import json
import pika

from decouple import config

from rest_framework import viewsets

from .models import Categoria, Producto, Mesa, Empleado, PedidoCabecera, PedidoDetalle
from .serializers import (
    CategoriaSerializer,
    ProductoSerializer,
    MesaSerializer,
    EmpleadoSerializer,
    PedidoCabeceraSerializer,
    PedidoDetalleSerializer,
)


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer


import json
from .redis_client import redis_client

CACHE_TTL_SEGUNDOS = 60


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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Mesa, PedidoCabecera
from .serializers import ComandaEntradaSerializer


class ComandaCreateView(APIView):
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
        properties=pika.BasicProperties(delivery_mode=2)  # persiste el mensaje en disco
    )
    conexion.close()


class ComandaCreateView(APIView):
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

        return Response(
            {'mensaje': 'Comanda validada, pendiente de encolar.'},
            status=status.HTTP_202_ACCEPTED
        )