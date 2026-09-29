import os
import json
import pika
from decouple import config

from rest_framework import viewsets, status
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
        super().perform_update(serializer)
        self._invalidar_cache_catalogo()
        print('[CACHE INVALIDADO] por actualizacion de producto')

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._invalidar_cache_catalogo()
        print('[CACHE INVALIDADO] por baja de producto')


class MesaViewSet(viewsets.ModelViewSet):
    queryset = Mesa.objects.all()
    serializer_class = MesaSerializer


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

        mesa = Mesa.objects.filter(numero=datos['mesa_id']).first()
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