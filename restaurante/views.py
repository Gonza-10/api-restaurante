import os
import re
import json
import uuid
import pika
from decouple import config

from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import FileResponse, Http404

from .models import Categoria, Producto, Mesa, Empleado, PedidoCabecera, PedidoDetalle, ComandaRecibida
from .serializers import (
    CategoriaSerializer,
    ProductoSerializer,
    MesaSerializer,
    EmpleadoSerializer,
    PedidoCabeceraSerializer,
    PedidoDetalleSerializer,
    ComandaEntradaSerializer,
    ComandaCocinaSerializer,
)
from .redis_client import redis_client

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
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer


class ProductoViewSet(viewsets.ModelViewSet):
    serializer_class = ProductoSerializer

    def get_queryset(self):
        queryset = Producto.objects.select_related('categoria').all()
        if self.action == 'list':
            incluir_inactivos = self.request.query_params.get('incluir_inactivos') == 'true'
            if not incluir_inactivos:
                queryset = queryset.filter(activo=True)

            categoria_id = self.request.query_params.get('categoria')
            vegetariano = self.request.query_params.get('vegetariano')
            celiaco = self.request.query_params.get('celiaco')
            if categoria_id:
                queryset = queryset.filter(categoria_id=categoria_id)
            if vegetariano == 'true':
                queryset = queryset.filter(es_vegetariano=True)
            if celiaco == 'true':
                queryset = queryset.filter(apto_celiaco=True)
        return queryset

    def list(self, request, *args, **kwargs):
        incluir_inactivos = request.query_params.get('incluir_inactivos') == 'true'
        sin_otros_filtros = len(request.query_params) <= 1
        usar_cache = sin_otros_filtros

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

    def get_queryset(self):
        queryset = Mesa.objects.all()
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


class EmpleadoViewSet(viewsets.ModelViewSet):
    queryset = Empleado.objects.select_related('rol').all()
    serializer_class = EmpleadoSerializer


class PedidoCabeceraViewSet(viewsets.ModelViewSet):
    queryset = PedidoCabecera.objects.select_related('mesa', 'empleado').prefetch_related('detalles__producto').all()
    serializer_class = PedidoCabeceraSerializer


class PedidoDetalleViewSet(viewsets.ModelViewSet):
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
    ).order_by('fecha_hora_recepcion')

    resultado = []
    for comanda in comandas:
        uuid_str = str(comanda.id_comanda_uuid)
        estado = redis_client.get(f'comanda:estado:{uuid_str}')

        if estado is None:
            continue

        detalles = comanda.pedido_cabecera.detalles.select_related('producto').all()
        items = [
            {'nombre': d.producto.nombre, 'precio': d.precio_unitario}
            for d in detalles
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
    def get(self, request):
        resultado = _armar_tablero_cocina()
        serializer = ComandaCocinaSerializer(resultado, many=True)
        return Response(serializer.data)


class ComandaEstadoUpdateView(APIView):
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
    def get(self, request, uuid_comanda):
        ruta = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'tickets', f'{uuid_comanda}.pdf'
        )
        if not os.path.exists(ruta):
            raise Http404('El ticket todavia no fue generado o la comanda no existe.')
        return FileResponse(open(ruta, 'rb'), content_type='application/pdf')