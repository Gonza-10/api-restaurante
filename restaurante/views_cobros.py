"""Vistas de cobros, caja y cotizacion."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE
from .cotizacion import BcraNoDisponible, actualizar_cotizaciones, estado_cotizaciones
from .serializers_cobros import EstadoCotizacionesSerializer


class CotizacionesView(APIView):
    """GET /cotizaciones. Publico (el cliente ve cuanto equivale su cuenta en USD, BRL y PYG). Devuelve siempre las tres
    monedas con su cotizacion vigente: ARS por 1 unidad, tomada del BCRA y actualizada sola cada 30 minutos (los fines de
    semana rige la ultima publicada). `valor` es null si todavia no se guardo ninguna. `desactualizada` avisa si hace mas
    de 2 horas que no se consulta al BCRA con exito. No hay forma de cargar una cotizacion a mano."""
    authentication_classes = []   # publico: un token vencido no debe impedir ver las cotizaciones
    roles_lectura = None

    def get(self, request):
        return Response(EstadoCotizacionesSerializer(estado_cotizaciones()).data)


class CotizacionesActualizarView(APIView):
    """POST /cotizaciones/actualizar. Admin y Gerente. Vuelve a consultar AHORA al BCRA (no carga ningun valor a mano) y
    guarda lo que haya cambiado. `502` si no se pudo consultar: las ultimas cotizaciones guardadas siguen vigentes."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request):
        try:
            resultado = actualizar_cotizaciones()
        except BcraNoDisponible as error:
            estado = EstadoCotizacionesSerializer(estado_cotizaciones(con_detalle_error=True)).data
            return Response(
                {'error': 'No se pudo consultar al BCRA. Siguen vigentes las ultimas cotizaciones guardadas.',
                 'detalle': str(error), **estado},
                status=status.HTTP_502_BAD_GATEWAY
            )
        estado = EstadoCotizacionesSerializer(estado_cotizaciones(con_detalle_error=True)).data
        return Response({
            'mensaje': 'Cotizaciones consultadas al BCRA.',
            'guardadas': resultado['guardadas'],
            'sin_cambios': resultado['sin_cambios'],
            **estado,
        })
