import os
import re
import json
import uuid
import secrets
import pika
from decouple import config

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction, IntegrityError
from django.db.models import Q, Prefetch
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import FileResponse, Http404

from .models import Categoria, Producto, Mesa, Empleado, Rol, PedidoCabecera, PedidoDetalle, ComandaRecibida
from .serializers import (
    CategoriaSerializer,
    ProductoSerializer,
    MesaSerializer,
    EmpleadoSerializer,
    RolSerializer,
    PedidoCabeceraSerializer,
    PedidoDetalleSerializer,
    ComandaEntradaSerializer,
    ComandaCocinaSerializer,
    SesionAbrirSerializer,
    AccesoClienteSerializer,
    HistorialMesaSerializer,
    ComandaHistorialSerializer,
    fecha_iso,
)
from .redis_client import redis_client
from .auth import (
    emitir_token, ttl_token_segundos,
    ADMIN_GERENTE, SOLO_GERENTE, SALON, COCINA, ROL_GERENTE, ROL_MOZO,
)
from .limites import superado, registrar_fallo, limpiar

CACHE_TTL_SEGUNDOS = 60

# ==================== IMAGENES DE PRODUCTO ====================
IMAGEN_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
IMAGEN_SUBCARPETA = 'productos'
IMAGEN_RUTA_LOCAL = re.compile(r'^/media/productos/[0-9a-f]{32}\.(jpg|png|webp)$')


def _detectar_extension_imagen(cabecera: bytes):
    """Detecta el formato real por los primeros bytes (no confiamos en el nombre ni en el Content-Type)."""
    if cabecera[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if cabecera[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP':
        return 'webp'
    return None


def _borrar_imagen_local(imagen_url):
    """Borra del disco una imagen subida al servidor. Ignora links externos y rutas que no coincidan."""
    if not imagen_url or not IMAGEN_RUTA_LOCAL.match(imagen_url):
        return
    ruta = os.path.join(settings.MEDIA_ROOT, IMAGEN_SUBCARPETA, os.path.basename(imagen_url))
    try:
        os.remove(ruta)
    except FileNotFoundError:
        pass


class CategoriaViewSet(viewsets.ModelViewSet):
    roles_lectura = None  # el menu es publico
    roles_escritura = ADMIN_GERENTE
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer


# ==================== FILTROS DEL CATALOGO ====================
ORDENES_PRODUCTO = {
    'precio': 'precio_actual',
    '-precio': '-precio_actual',
    'nombre': 'nombre',
    '-nombre': '-nombre',
}
PARAMS_SIN_CACHE_PERMITIDOS = {'incluir_inactivos'}


def _es_verdadero(valor):
    return (valor or '').strip().lower() in ('true', '1')


def _parsear_ids(valor, nombre_param):
    try:
        ids = [int(x) for x in valor.split(',') if x.strip() != '']
    except ValueError:
        ids = []
    if not ids:
        raise ValidationError({nombre_param: 'Debe ser un id o varios separados por coma (ej: 1 o 1,3).'})
    return ids


def _parsear_precio(valor, nombre_param):
    try:
        numero = Decimal(valor)
    except InvalidOperation:
        raise ValidationError({nombre_param: 'Debe ser un numero (ej: 8500 o 8500.50).'})
    if not numero.is_finite() or numero < 0:
        raise ValidationError({nombre_param: 'Debe ser un numero mayor o igual a 0.'})
    return numero


class ProductoViewSet(viewsets.ModelViewSet):
    serializer_class = ProductoSerializer
    roles_lectura = None  # el menu es publico
    roles_escritura = ADMIN_GERENTE

    def get_queryset(self):
        queryset = Producto.objects.select_related('categoria').all()
        if self.action != 'list':
            return queryset

        p = self.request.query_params

        if not _es_verdadero(p.get('incluir_inactivos')):
            queryset = queryset.filter(activo=True)

        # Todos los filtros se combinan entre si (AND)
        if p.get('categoria'):
            queryset = queryset.filter(categoria_id__in=_parsear_ids(p['categoria'], 'categoria'))
        if _es_verdadero(p.get('vegetariano')):
            queryset = queryset.filter(es_vegetariano=True)
        if _es_verdadero(p.get('sin_tacc')) or _es_verdadero(p.get('celiaco')):
            queryset = queryset.filter(apto_celiaco=True)

        texto = (p.get('buscar') or '').strip()
        if texto:
            queryset = queryset.filter(Q(nombre__icontains=texto) | Q(descripcion__icontains=texto))

        if p.get('precio_min'):
            queryset = queryset.filter(precio_actual__gte=_parsear_precio(p['precio_min'], 'precio_min'))
        if p.get('precio_max'):
            queryset = queryset.filter(precio_actual__lte=_parsear_precio(p['precio_max'], 'precio_max'))

        orden = p.get('orden')
        if orden:
            if orden not in ORDENES_PRODUCTO:
                raise ValidationError({'orden': f"Valor invalido. Opciones: {', '.join(ORDENES_PRODUCTO)}."})
            return queryset.order_by(ORDENES_PRODUCTO[orden], 'id')
        return queryset.order_by('id')

    def list(self, request, *args, **kwargs):
        incluir_inactivos = _es_verdadero(request.query_params.get('incluir_inactivos'))
        # el cache solo vale para el listado completo: cualquier filtro u orden lo saltea
        usar_cache = set(request.query_params.keys()) <= PARAMS_SIN_CACHE_PERMITIDOS

        cache_key = 'catalogo:productos:admin' if incluir_inactivos else 'catalogo:productos:publico'

        if usar_cache:
            datos_cacheados = redis_client.get(cache_key)
            if datos_cacheados:
                print(f'[CACHE HIT] {cache_key}')
                return Response(json.loads(datos_cacheados))
            print(f'[CACHE MISS] {cache_key}')

        respuesta = super().list(request, *args, **kwargs)

        if usar_cache:
            redis_client.setex(cache_key, CACHE_TTL_SEGUNDOS, json.dumps(respuesta.data))

        return respuesta

    def _invalidar_cache_catalogo(self):
        redis_client.delete('catalogo:productos:publico', 'catalogo:productos:admin')

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._invalidar_cache_catalogo()
        print('[CACHE INVALIDADO] por creacion de producto')

    def perform_update(self, serializer):
        imagen_anterior = serializer.instance.imagen_url
        super().perform_update(serializer)
        if serializer.instance.imagen_url != imagen_anterior:
            _borrar_imagen_local(imagen_anterior)
        self._invalidar_cache_catalogo()
        print('[CACHE INVALIDADO] por actualizacion de producto')

    @action(detail=True, methods=['post', 'delete'], url_path='imagen',
            parser_classes=[MultiPartParser, FormParser])
    def imagen(self, request, pk=None):
        """POST (multipart, campo 'imagen'): sube una foto propia. DELETE: quita la imagen del producto."""
        producto = self.get_object()
        anterior = producto.imagen_url

        if request.method == 'DELETE':
            producto.imagen_url = None
            producto.save(update_fields=['imagen_url'])
            _borrar_imagen_local(anterior)
            self._invalidar_cache_catalogo()
            return Response(status=status.HTTP_204_NO_CONTENT)

        archivo = request.FILES.get('imagen')
        if archivo is None:
            return Response({'error': "Falta el archivo. Enviar multipart/form-data con el campo 'imagen'."},
                            status=status.HTTP_400_BAD_REQUEST)
        if archivo.size > IMAGEN_MAX_BYTES:
            return Response({'error': 'La imagen supera el maximo de 2 MB.'},
                            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        extension = _detectar_extension_imagen(archivo.read(12))
        archivo.seek(0)
        if extension is None:
            return Response({'error': 'Formato no permitido. Solo JPG, PNG o WEBP.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # el nombre lo genera el servidor: el del cliente se descarta (evita pisar archivos y rutas raras)
        nombre = f'{uuid.uuid4().hex}.{extension}'
        carpeta = os.path.join(settings.MEDIA_ROOT, IMAGEN_SUBCARPETA)
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, nombre), 'wb') as destino:
            for trozo in archivo.chunks():
                destino.write(trozo)

        producto.imagen_url = f'/media/{IMAGEN_SUBCARPETA}/{nombre}'
        producto.save(update_fields=['imagen_url'])
        _borrar_imagen_local(anterior)
        self._invalidar_cache_catalogo()
        return Response(ProductoSerializer(producto).data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._invalidar_cache_catalogo()
        print('[CACHE INVALIDADO] por baja de producto')


class MesaViewSet(viewsets.ModelViewSet):
    serializer_class = MesaSerializer
    roles_lectura = SALON
    roles_escritura = ADMIN_GERENTE

    def get_queryset(self):
        queryset = Mesa.objects.prefetch_related(Prefetch(
            'pedidos',
            queryset=PedidoCabecera.objects.filter(estado='Abierto').select_related('empleado'),
            to_attr='sesiones_abiertas',
        ))
        if self.action == 'list':
            incluir_inactivas = self.request.query_params.get('incluir_inactivas') == 'true'
            if not incluir_inactivas:
                queryset = queryset.filter(activa=True)
        return queryset

    def destroy(self, request, *args, **kwargs):
        # baja lógica: se conserva el historial de sesiones de la mesa
        mesa = self.get_object()
        if mesa.estado:
            return Response(
                {'error': 'No se puede dar de baja una mesa ocupada. Cierre primero su sesion.'},
                status=status.HTTP_409_CONFLICT
            )
        mesa.activa = False
        mesa.save(update_fields=['activa'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class RolViewSet(viewsets.ReadOnlyModelViewSet):
    """Lista de roles, para armar el formulario de empleados (el que los gestiona es el Gerente)."""
    queryset = Rol.objects.order_by('id')
    serializer_class = RolSerializer
    roles_lectura = SOLO_GERENTE


class EmpleadoViewSet(viewsets.ModelViewSet):
    serializer_class = EmpleadoSerializer
    roles_lectura = SOLO_GERENTE
    roles_escritura = SOLO_GERENTE

    def get_queryset(self):
        queryset = Empleado.objects.select_related('rol').order_by('id')
        if self.action == 'list' and not _es_verdadero(self.request.query_params.get('incluir_inactivos')):
            queryset = queryset.filter(activo=True)
        return queryset

    def _quedan_otros_gerentes(self, empleado):
        return Empleado.objects.filter(rol__nombre=ROL_GERENTE, activo=True).exclude(id=empleado.id).exists()

    def perform_update(self, serializer):
        actual = serializer.instance
        nuevo_activo = serializer.validated_data.get('activo', actual.activo)
        nuevo_rol = serializer.validated_data.get('rol', actual.rol)

        if actual.id == self.request.user.id and (not nuevo_activo or nuevo_rol.id != actual.rol_id):
            raise ValidationError({'error': 'No puede darse de baja ni cambiarse el rol a si mismo.'})

        era_gerente_activo = actual.activo and actual.rol.nombre == ROL_GERENTE
        sigue_siendolo = nuevo_activo and nuevo_rol.nombre == ROL_GERENTE
        if era_gerente_activo and not sigue_siendolo and not self._quedan_otros_gerentes(actual):
            raise ValidationError({'error': 'Debe quedar al menos un Gerente activo.'})

        super().perform_update(serializer)

    def destroy(self, request, *args, **kwargs):
        # baja logica: el empleado figura en sesiones de mesa historicas y no se puede borrar de la base
        empleado = self.get_object()
        if empleado.id == request.user.id:
            return Response({'error': 'No puede darse de baja a si mismo.'}, status=status.HTTP_409_CONFLICT)
        if empleado.rol.nombre == ROL_GERENTE and empleado.activo and not self._quedan_otros_gerentes(empleado):
            return Response({'error': 'Debe quedar al menos un Gerente activo.'}, status=status.HTTP_409_CONFLICT)
        empleado.activo = False
        empleado.save(update_fields=['activo'])
        return Response(status=status.HTTP_204_NO_CONTENT)


PIN_MAX_FALLOS = 10
PIN_VENTANA_SEGUNDOS = 300


def _ip(request):
    return request.META.get('REMOTE_ADDR', 'desconocida')


def _generar_pin_libre():
    """PIN de 4 digitos que no este en uso por ninguna otra sesion abierta."""
    en_uso = set(PedidoCabecera.objects.filter(estado='Abierto').values_list('codigo_pin', flat=True))
    for _ in range(100):
        pin = f'{secrets.randbelow(10000):04d}'
        if pin not in en_uso:
            return pin
    return None


class PedidoCabeceraViewSet(viewsets.ModelViewSet):
    """Sesiones de mesa. Se abren y se cierran SOLO con /abrir y /cerrar; el resto es lectura.
    Un Mozo ve unicamente sus propias sesiones; Admin y Gerente ven todas."""
    serializer_class = PedidoCabeceraSerializer
    roles_lectura = SALON
    roles_escritura = SALON
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        queryset = PedidoCabecera.objects.select_related('mesa', 'empleado').prefetch_related(
            'detalles__producto').order_by('-id')
        if getattr(self.request.user, 'rol', None) == ROL_MOZO:
            queryset = queryset.filter(empleado_id=self.request.user.id)
        if self.action == 'list':
            p = self.request.query_params
            estado = (p.get('estado') or '').strip().lower()
            if estado:
                if estado not in ('abierto', 'cerrado'):
                    raise ValidationError({'estado': "Valores validos: 'Abierto' o 'Cerrado'."})
                queryset = queryset.filter(estado__iexact=estado)
            if p.get('mesa'):
                queryset = queryset.filter(mesa__numero__in=_parsear_ids(p['mesa'], 'mesa'))
        return queryset

    def create(self, request, *args, **kwargs):
        return Response(
            {'error': 'Para abrir una mesa use POST /sesiones-mesa/abrir.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    @action(detail=False, methods=['post'], url_path='abrir')
    def abrir(self, request):
        """El mozo sienta clientes: indica mesa y cantidad de comensales. El servidor genera el PIN,
        toma al mozo del token y ocupa la mesa, todo en una sola operacion."""
        entrada = SesionAbrirSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        numero = entrada.validated_data['numero_mesa']
        comensales = entrada.validated_data['cantidad_comensales']

        mesa = Mesa.objects.filter(numero=numero, activa=True).first()
        if mesa is None:
            return Response({'error': f'No existe la mesa numero {numero}.'}, status=status.HTTP_404_NOT_FOUND)
        if comensales > mesa.capacidad_maxima:
            return Response(
                {'error': f'La mesa {numero} admite hasta {mesa.capacidad_maxima} comensales.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        for _ in range(5):
            if mesa.estado or PedidoCabecera.objects.filter(mesa=mesa, estado='Abierto').exists():
                return Response({'error': f'La mesa {numero} ya esta ocupada.'}, status=status.HTTP_409_CONFLICT)
            pin = _generar_pin_libre()
            if pin is None:
                return Response({'error': 'No hay PINs disponibles.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            try:
                with transaction.atomic():
                    sesion = PedidoCabecera.objects.create(
                        mesa=mesa,
                        empleado=request.user.empleado,
                        codigo_pin=pin,
                        fecha_hora_apertura=timezone.now(),
                        cantidad_comensales=comensales,
                        estado='Abierto',
                    )
                    mesa.estado = True
                    mesa.save(update_fields=['estado'])
            except IntegrityError:
                # otra apertura simultanea tomo la misma mesa o el mismo PIN: se vuelve a evaluar
                mesa.refresh_from_db()
                continue
            return Response(PedidoCabeceraSerializer(sesion).data, status=status.HTTP_201_CREATED)

        return Response({'error': 'No se pudo abrir la mesa. Intente de nuevo.'}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=['get'], url_path='comandas')
    def comandas(self, request, pk=None):
        """Comandas de la sesion con sus items y estado (un Mozo solo ve las de sus propias sesiones)."""
        sesion = self.get_object()
        return Response(ComandaHistorialSerializer(_comandas_de_sesion(sesion), many=True).data)

    @action(detail=True, methods=['post'], url_path='cerrar')
    def cerrar(self, request, pk=None):
        """Cierra la sesion: la fecha la pone el servidor y la mesa queda libre, en una sola operacion."""
        sesion = self.get_object()
        if sesion.estado != 'Abierto':
            return Response({'error': 'La sesion ya esta cerrada.'}, status=status.HTTP_409_CONFLICT)
        with transaction.atomic():
            sesion.estado = 'Cerrado'
            sesion.fecha_hora_cierre = timezone.now()
            sesion.save(update_fields=['estado', 'fecha_hora_cierre'])
            mesa = sesion.mesa
            mesa.estado = False
            mesa.save(update_fields=['estado'])
        return Response(PedidoCabeceraSerializer(sesion).data)


class PedidoDetalleViewSet(viewsets.ModelViewSet):
    roles_lectura = SALON
    roles_escritura = SALON
    queryset = PedidoDetalle.objects.select_related('producto', 'pedido_cabecera').all()
    serializer_class = PedidoDetalleSerializer


# ==================== RABBITMQ (publicadores) ====================

def _publicar_en_rabbitmq(payload: dict):
    parametros = pika.ConnectionParameters(
        host='localhost',
        credentials=pika.PlainCredentials(
            config('RABBIT_USER'), config('RABBIT_PASS')
        )
    )
    conexion = pika.BlockingConnection(parametros)
    canal = conexion.channel()
    canal.queue_declare(queue='comandas_pendientes', durable=True)
    canal.basic_publish(
        exchange='',
        routing_key='comandas_pendientes',
        body=json.dumps(payload, default=str),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conexion.close()


def _publicar_evento_comanda_lista(id_comanda_uuid: str):
    parametros = pika.ConnectionParameters(
        host='localhost',
        credentials=pika.PlainCredentials(
            config('RABBIT_USER'), config('RABBIT_PASS')
        )
    )
    conexion = pika.BlockingConnection(parametros)
    canal = conexion.channel()
    canal.queue_declare(queue='comandas_listas', durable=True)
    canal.basic_publish(
        exchange='',
        routing_key='comandas_listas',
        body=json.dumps({'id_comanda_uuid': id_comanda_uuid}),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conexion.close()


# ==================== TABLERO DE COCINA (armado compartido) ====================

def _armar_tablero_cocina():
    comandas = ComandaRecibida.objects.select_related(
        'pedido_cabecera__mesa'
    ).prefetch_related('detalles__producto').order_by('fecha_hora_recepcion')

    resultado = []
    for comanda in comandas:
        uuid_str = str(comanda.id_comanda_uuid)
        estado = redis_client.get(f'comanda:estado:{uuid_str}')

        if estado is None:
            continue

        # solo los items de ESTA comanda (no los de toda la sesion de la mesa)
        items = [
            {'nombre': d.producto.nombre, 'precio': d.precio_unitario, 'cantidad': d.cantidad}
            for d in comanda.detalles.all()
        ]

        resultado.append({
            'id_comanda_uuid': uuid_str,
            'mesa_id': str(comanda.pedido_cabecera.mesa.numero).zfill(2),
            'items': items,
            'estado': estado,
            'timestamp': comanda.fecha_hora_recepcion,
        })

    return resultado


# ==================== COMANDAS ====================

class ComandaCreateView(APIView):
    roles_lectura = None   # GET: tablero de cocina
    roles_escritura = None   # POST: el cliente envia su comanda (mas adelante, protegido por PIN)

    def get(self, request):
        resultado = _armar_tablero_cocina()
        serializer = ComandaCocinaSerializer(resultado, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ComandaEntradaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        mesa = Mesa.objects.filter(numero=datos['mesa_id'], activa=True).first()
        if mesa is None:
            return Response(
                {'error': f"No existe la mesa numero {datos['mesa_id']}."},
                status=status.HTTP_404_NOT_FOUND
            )

        pedido_cabecera = PedidoCabecera.objects.filter(
            mesa=mesa, estado='Abierto'
        ).first()

        if pedido_cabecera is None:
            return Response(
                {'error': 'Esta mesa no tiene una sesion abierta. Avisa al mozo.'},
                status=status.HTTP_409_CONFLICT
            )

        clave_pin = f'pin:fallos:{_ip(request)}'
        if superado(clave_pin, PIN_MAX_FALLOS):
            return Response(
                {'error': 'Demasiados intentos con PIN incorrecto. Espere unos minutos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        if not secrets.compare_digest(pedido_cabecera.codigo_pin.strip().encode(), datos['pin'].encode()):
            registrar_fallo(clave_pin, PIN_VENTANA_SEGUNDOS)
            return Response({'error': 'PIN incorrecto.'}, status=status.HTTP_403_FORBIDDEN)

        payload = {
            'id_comanda_uuid': str(datos['id_comanda_uuid']),
            'id_pedido_cabecera': pedido_cabecera.id,
            'items': [{'id': item['id']} for item in datos['items']],
        }

        try:
            _publicar_en_rabbitmq(payload)
        except pika.exceptions.AMQPConnectionError:
            return Response(
                {'error': 'No se pudo conectar con el servidor de mensajeria. Intenta de nuevo.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response(
            {'mensaje': 'Comanda encolada correctamente.'},
            status=status.HTTP_202_ACCEPTED
        )


class TableroCocinaView(APIView):
    roles_lectura = None

    def get(self, request):
        resultado = _armar_tablero_cocina()
        serializer = ComandaCocinaSerializer(resultado, many=True)
        return Response(serializer.data)


class ComandaEstadoUpdateView(APIView):
    roles_escritura = None
    ESTADOS_VALIDOS = {'pendiente', 'proceso', 'listo', 'entregado'}

    def patch(self, request, uuid_comanda):
        nuevo_estado = request.data.get('estado')

        if nuevo_estado not in self.ESTADOS_VALIDOS:
            return Response(
                {'error': f'Estado invalido. Debe ser uno de: {", ".join(self.ESTADOS_VALIDOS)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        clave = f'comanda:estado:{uuid_comanda}'
        if not redis_client.exists(clave):
            return Response(
                {'error': 'La comanda no existe o ya fue cerrada.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if nuevo_estado == 'entregado':
            redis_client.delete(clave)
        else:
            redis_client.set(clave, nuevo_estado)

        if nuevo_estado == 'listo':
            try:
                _publicar_evento_comanda_lista(str(uuid_comanda))
            except pika.exceptions.AMQPConnectionError:
                pass

        return Response({'mensaje': f'Comanda actualizada a estado: {nuevo_estado}'})


class TicketPDFView(APIView):
    roles_lectura = None  # el cliente descarga su comprobante; el nombre del archivo es un UUID

    def get(self, request, uuid_comanda):
        ruta = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'tickets', f'{uuid_comanda}.pdf'
        )
        if not os.path.exists(ruta):
            raise Http404('El ticket todavia no fue generado o la comanda no existe.')
        return FileResponse(open(ruta, 'rb'), content_type='application/pdf')


# ==================== LOGIN ====================

LOGIN_MAX_FALLOS = 5
LOGIN_VENTANA_SEGUNDOS = 300
_HASH_SENUELO = []


def _hash_senuelo():
    # se verifica contra este hash cuando el usuario no existe, para que tarde lo mismo
    # y no se pueda descubrir que usuarios existen midiendo el tiempo de respuesta
    if not _HASH_SENUELO:
        _HASH_SENUELO.append(make_password('senuelo-sin-uso'))
    return _HASH_SENUELO[0]


class LoginView(APIView):
    authentication_classes = []  # un token vencido en el encabezado no debe impedir volver a loguearse
    permission_classes = []

    def post(self, request):
        usuario = str(request.data.get('usuario') or '').strip()
        contrasena = str(request.data.get('contrasena') or '')
        if not usuario or not contrasena:
            return Response({'error': 'Usuario y contrasena son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        clave_fallos = f'login:fallos:{usuario.lower()}'
        if superado(clave_fallos, LOGIN_MAX_FALLOS):
            return Response(
                {'error': 'Demasiados intentos fallidos. Espere unos minutos e intente de nuevo.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        empleado = Empleado.objects.select_related('rol').filter(usuario=usuario, activo=True).first()
        hash_guardado = empleado.contrasena_hash if empleado else _hash_senuelo()
        correcta = check_password(contrasena, hash_guardado)

        if empleado is None or not correcta:
            registrar_fallo(clave_fallos, LOGIN_VENTANA_SEGUNDOS)
            return Response({'error': 'Usuario o contrasena incorrectos.'}, status=status.HTTP_401_UNAUTHORIZED)

        limpiar(clave_fallos)

        return Response({
            'token': emitir_token(empleado),
            'tipo': 'Bearer',
            'expira_en_segundos': ttl_token_segundos(),
            'empleado': _datos_empleado(empleado),
        })


def _datos_empleado(empleado):
    return {
        'id': empleado.id,
        'nombre': empleado.nombre,
        'apellido': empleado.apellido,
        'usuario': empleado.usuario,
        'rol': empleado.rol.nombre,
    }


class PerfilView(APIView):
    """GET /me: quien soy segun el token (cualquier rol)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_datos_empleado(request.user.empleado))


class AccesoMesaView(APIView):
    """El cliente ingresa el PIN que le dio el mozo: devuelve a que mesa pertenece (solo si la sesion esta abierta)."""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        pin = str(request.data.get('pin') or '').strip()
        clave_pin = f'pin:fallos:{_ip(request)}'
        if superado(clave_pin, PIN_MAX_FALLOS):
            return Response(
                {'error': 'Demasiados intentos con PIN incorrecto. Espere unos minutos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        sesion = None
        if re.fullmatch(r'\d{4}', pin):
            sesion = PedidoCabecera.objects.select_related('mesa', 'empleado').filter(
                estado='Abierto', codigo_pin=pin, mesa__activa=True
            ).first()
        if sesion is None:
            registrar_fallo(clave_pin, PIN_VENTANA_SEGUNDOS)
            return Response(
                {'error': 'PIN incorrecto o la mesa no tiene una sesion abierta.'},
                status=status.HTTP_403_FORBIDDEN
            )
        # el contador no se reinicia al acertar: asi nadie resetea el limite usando su propio PIN valido
        return Response({
            'numero_mesa': sesion.mesa.numero,
            'cantidad_comensales': sesion.cantidad_comensales,
            'mozo_nombre': f'{sesion.empleado.nombre} {sesion.empleado.apellido}',
            'fecha_hora_inicio': fecha_iso(sesion.fecha_hora_apertura),
            'solicita_cuenta': sesion.fecha_hora_solicita_cuenta is not None,
        })


# ==================== CLIENTE DE MESA (sin login: mesa + PIN) ====================

def _sesion_cliente(request, numero_mesa, pin):
    """Valida que la mesa tenga una sesion abierta y que el PIN sea el suyo (con limite de intentos por IP).
    Devuelve (sesion, None) o (None, Response de error)."""
    clave_pin = f'pin:fallos:{_ip(request)}'
    if superado(clave_pin, PIN_MAX_FALLOS):
        return None, Response(
            {'error': 'Demasiados intentos con PIN incorrecto. Espere unos minutos.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    mesa = Mesa.objects.filter(numero=numero_mesa, activa=True).first()
    if mesa is None:
        return None, Response({'error': f'No existe la mesa numero {numero_mesa}.'}, status=status.HTTP_404_NOT_FOUND)

    sesion = PedidoCabecera.objects.select_related('mesa', 'empleado').filter(mesa=mesa, estado='Abierto').first()
    if sesion is None:
        return None, Response(
            {'error': 'Esta mesa no tiene una sesion abierta. Avisa al mozo.'},
            status=status.HTTP_409_CONFLICT
        )

    if not secrets.compare_digest(sesion.codigo_pin.strip().encode(), pin.encode()):
        registrar_fallo(clave_pin, PIN_VENTANA_SEGUNDOS)
        return None, Response({'error': 'PIN incorrecto.'}, status=status.HTTP_403_FORBIDDEN)

    return sesion, None


def _comandas_de_sesion(sesion):
    """Comandas de una sesion con sus items y su estado. El estado vive en Redis mientras la comanda
    esta activa; cuando ya no esta ahi, la comanda fue entregada."""
    comandas = sesion.comandas.prefetch_related('detalles__producto').order_by('fecha_hora_recepcion')
    resultado = []
    for comanda in comandas:
        items = [
            {
                'nombre': d.producto.nombre,
                'precio': d.precio_unitario,
                'cantidad': d.cantidad,
                'sub_total': d.sub_total,
            }
            for d in comanda.detalles.all()
        ]
        resultado.append({
            'id_comanda_uuid': str(comanda.id_comanda_uuid),
            'estado': redis_client.get(f'comanda:estado:{comanda.id_comanda_uuid}') or 'entregado',
            'timestamp': comanda.fecha_hora_recepcion,
            'items': items,
            'total': sum((i['sub_total'] for i in items), Decimal('0.00')),
        })
    return resultado


class SolicitarCuentaView(APIView):
    """El cliente avisa al mozo que quiere la cuenta. Es idempotente: pedirla dos veces conserva la primera hora."""
    authentication_classes = []  # un token vencido no debe impedir pedir la cuenta
    roles_lectura = None
    roles_escritura = None  # publico, protegido por el PIN de la mesa

    def post(self, request):
        entrada = AccesoClienteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
        if error is not None:
            return error

        if sesion.fecha_hora_solicita_cuenta is None:
            sesion.fecha_hora_solicita_cuenta = timezone.now()
            sesion.save(update_fields=['fecha_hora_solicita_cuenta'])

        return Response({
            'mensaje': 'Cuenta solicitada. El mozo ya fue avisado.',
            'solicita_cuenta': True,
            'fecha_hora_solicita_cuenta': fecha_iso(sesion.fecha_hora_solicita_cuenta),
        })


class HistorialMesaView(APIView):
    """El cliente consulta las comandas de su mesa y en que estado estan. Todos los dispositivos de la mesa
    (mismo PIN) ven lo mismo. Es POST para que el PIN viaje en el cuerpo y no en la URL."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None  # publico, protegido por el PIN de la mesa

    def post(self, request):
        entrada = AccesoClienteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
        if error is not None:
            return error

        comandas = _comandas_de_sesion(sesion)
        return Response(HistorialMesaSerializer({
            'numero_mesa': sesion.mesa.numero,
            'total': sum((c['total'] for c in comandas), Decimal('0.00')),
            'comandas': comandas,
        }).data)
