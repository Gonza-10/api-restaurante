"""Disponibilidad de los productos y aviso en tiempo real del menu."""
import logging

from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import COCINA
from .catalogo import CANAL_CAMBIOS, CLAVE_VERSION, invalidar_cache_catalogo, version_catalogo
from .models import Producto
from .redis_client import nuevo_cliente
from .serializers import ProductoSerializer
from .sse import CanalRedis, FlujoEventos, RegistroConexiones

logger = logging.getLogger(__name__)
registro_conexiones = RegistroConexiones()


@require_GET
def catalogo_eventos(request):
    """GET /catalogo/eventos (publico). Flujo SSE: manda la version del menu al conectar y cada vez que cambia.
    Es una vista de Django (no de DRF): DRF rechazaria con 406 el encabezado Accept: text/event-stream."""
    ip = request.META.get('REMOTE_ADDR', '?')
    if not registro_conexiones.tomar(ip):
        respuesta = JsonResponse(
            {'error': 'Demasiadas conexiones en tiempo real. Consultar GET /catalogo/version cada pocos segundos.'},
            status=503
        )
        respuesta['Retry-After'] = '10'
        return respuesta

    # la conexion con Redis se abre ACA, antes de contestar: si falla, el cliente recibe un 503 claro (y usa
    # /catalogo/version) en vez de un flujo vacio
    canal = None
    try:
        canal = CanalRedis(nuevo_cliente, CANAL_CAMBIOS, CLAVE_VERSION)
        flujo = FlujoEventos(canal=canal, ip=ip, registro=registro_conexiones)
        respuesta = StreamingHttpResponse(flujo, content_type='text/event-stream; charset=utf-8')
    except Exception:
        logger.exception('No se pudo abrir el flujo de eventos del catalogo')
        if canal is not None:
            canal.cerrar()
        registro_conexiones.soltar(ip)
        respuesta = JsonResponse(
            {'error': 'El aviso en tiempo real no esta disponible. Consultar GET /catalogo/version cada pocos segundos.'},
            status=503
        )
        respuesta['Retry-After'] = '10'
        return respuesta
    respuesta['Cache-Control'] = 'no-cache, no-transform'
    respuesta['X-Accel-Buffering'] = 'no'  # por si hay un proxy (nginx) adelante: que no acumule la salida
    return respuesta


class CatalogoVersionView(APIView):
    """GET /catalogo/version (publico). Respaldo del flujo SSE: si el numero cambio, volver a pedir /productos."""
    authentication_classes = []  # un token vencido no debe impedir consultar el menu
    roles_lectura = None
    roles_escritura = None

    def get(self, request):
        return Response({'version': version_catalogo()})


class ProductoDisponibilidadView(APIView):
    """POST /productos/<id>/agotar y /productos/<id>/reactivar. Cocina, Admin y Gerente.
    - agotar: Cocina marca el plato como "sin insumos". Desaparece del menu al instante.
    - reactivar: lo vuelve a ofrecer. No se puede mientras el stock no alcance para prepararlo (Disponible = 0).
    El stock NUNCA reactiva solo un plato agotado a mano: solo avisa que ya se puede reactivar."""
    roles_lectura = COCINA
    roles_escritura = COCINA
    accion = None  # 'agotar' o 'reactivar' (se fija en urls.py)

    def post(self, request, pk):
        producto = get_object_or_404(Producto.objects.select_related('categoria', 'empleado_agotado'), pk=pk)

        if self.accion == 'agotar':
            if not producto.agotado_manual:
                producto.agotado_manual = True
                producto.fecha_hora_agotado = timezone.now()
                producto.empleado_agotado = request.user.empleado
                producto.save(update_fields=['agotado_manual', 'fecha_hora_agotado', 'empleado_agotado'])
                invalidar_cache_catalogo()
        else:
            if producto.agotado_manual:
                if not producto.disponible:
                    return Response(
                        {'error': 'No se puede reactivar: no hay insumos suficientes para prepararlo.'},
                        status=status.HTTP_409_CONFLICT
                    )
                producto.agotado_manual = False
                producto.fecha_hora_agotado = None
                producto.empleado_agotado = None
                producto.save(update_fields=['agotado_manual', 'fecha_hora_agotado', 'empleado_agotado'])
                invalidar_cache_catalogo()

        return Response(ProductoSerializer(producto, context={'request': request}).data)
