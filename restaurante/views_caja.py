"""Vistas de caja: abrir, cerrar con arqueo por moneda, movimientos de efectivo e historial."""
from datetime import date

from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, SALON
from .caja import (
    ReglaCaja, abrir_caja, caja_abierta, cerrar_caja, registrar_movimiento_manual,
)
from .caja import resumen_arqueo
from .caja_calculos import (
    CajaInvalida, TIPOS_MOVIMIENTO, advertencias_de_diferencias, validar_moneda, validar_monto, validar_montos_por_moneda,
)
from .models import Caja, MovimientoCaja
from .serializers_cobros import CajaDetalleSerializer, CajaResumenSerializer, MovimientoCajaSerializer


def _invalido(campo, error):
    return ValidationError({campo: str(error)})


def _conflicto(error):
    return Response({'error': error.mensaje, **error.extra}, status=status.HTTP_409_CONFLICT)


def _cuerpo(request):
    return request.data if isinstance(request.data, dict) else {}


def _con_empleados(queryset):
    return queryset.select_related('empleado_apertura', 'empleado_cierre')


class CajaActualView(APIView):
    """GET /caja/actual. Mozo, Admin y Gerente. El mozo solo necesita saber si la caja esta abierta (sin ella no se puede
    cobrar), asi que ve unicamente `abierta`. Admin y Gerente ven ademas la caja con su arqueo (esperado por moneda)."""
    roles_lectura = SALON

    def get(self, request):
        caja = caja_abierta()
        if request.user.rol not in ADMIN_GERENTE:
            return Response({'abierta': caja is not None})
        return Response({
            'abierta': caja is not None,
            'caja': CajaDetalleSerializer(caja).data if caja else None,
        })


class CajaAbrirView(APIView):
    """POST /caja/abrir. Admin y Gerente. Cuerpo opcional: {"montos": {"ARS": 10000, "USD": 50, "BRL": 0, "PYG": 0}} con el
    efectivo inicial de cada moneda (las que no se mencionan arrancan en 0). Se puede abrir con la jornada cerrada."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request):
        try:
            montos = validar_montos_por_moneda(_cuerpo(request).get('montos'))
        except CajaInvalida as error:
            raise _invalido('montos', error)
        try:
            caja = abrir_caja(request.user.empleado, montos)
        except ReglaCaja as error:
            return _conflicto(error)
        caja = _con_empleados(Caja.objects).get(pk=caja.pk)
        return Response(CajaDetalleSerializer(caja).data, status=status.HTTP_201_CREATED)


class CajaCerrarView(APIView):
    """POST /caja/cerrar. Admin y Gerente. Cuerpo:
    {"montos": {"ARS": ..., "USD": ..., "BRL": ..., "PYG": ...}, "mercado_pago": 15000}
    - `montos`: lo CONTADO en el cajon en cada moneda (las cuatro; 0 si no hay).
    - `mercado_pago`: lo que figura acreditado en la cuenta de Mercado Pago por los cobros de esta caja (pesos). Es
      obligatorio si el sistema registro cobros digitales (hay que mirar la cuenta); si no hubo, se puede omitir.
    Devuelve el arqueo de cada medio (esperado, informado y diferencia) y el total en pesos. Una diferencia no impide
    cerrar: queda registrada y se avisa en `advertencias`."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request):
        cuerpo = _cuerpo(request)
        try:
            declarado = validar_montos_por_moneda(cuerpo.get('montos'), obligatorias=True)
        except CajaInvalida as error:
            raise _invalido('montos', error)
        try:
            caja = cerrar_caja(request.user.empleado, declarado, cuerpo.get('mercado_pago'))
        except CajaInvalida as error:
            raise _invalido('mercado_pago', error)
        except ReglaCaja as error:
            return _conflicto(error)
        resumen = resumen_arqueo(caja)
        caja._arqueo_cache = resumen
        datos = dict(CajaDetalleSerializer(caja).data)
        datos['advertencias'] = advertencias_de_diferencias(resumen)
        return Response(datos)


class CajaMovimientosView(APIView):
    """Movimientos de efectivo de la caja ABIERTA. Admin y Gerente.
    GET  /caja/movimientos -> los de la caja abierta (409 si no hay).
    POST /caja/movimientos -> ingreso o egreso manual: {"tipo": "Ingreso"|"Egreso", "moneda": "ARS", "monto": 500,
    "descripcion": "Cambio para el cajon"}. La descripcion es obligatoria (queda para la auditoria). Un egreso no puede
    sacar mas efectivo del que hay en esa moneda."""
    roles_lectura = ADMIN_GERENTE
    roles_escritura = ADMIN_GERENTE

    def get(self, request):
        caja = caja_abierta()
        if caja is None:
            return Response({'error': 'No hay una caja abierta.'}, status=status.HTTP_409_CONFLICT)
        movimientos = MovimientoCaja.objects.filter(caja=caja).select_related('empleado').order_by('-id')
        return Response(MovimientoCajaSerializer(movimientos, many=True).data)

    def post(self, request):
        datos = _cuerpo(request)
        tipo = str(datos.get('tipo') or '').strip().capitalize()
        if tipo not in TIPOS_MOVIMIENTO:
            raise ValidationError({'tipo': "Valores validos: 'Ingreso' o 'Egreso'."})
        try:
            moneda = validar_moneda(datos.get('moneda'))
        except CajaInvalida as error:
            raise _invalido('moneda', error)
        try:
            monto = validar_monto(datos.get('monto'), 'monto', positivo=True)
        except CajaInvalida as error:
            raise _invalido('monto', error)
        descripcion = str(datos.get('descripcion') or '').strip()
        if not descripcion:
            raise ValidationError({'descripcion': 'La descripcion es obligatoria (queda registrada para la auditoria).'})
        if len(descripcion) > 200:
            raise ValidationError({'descripcion': 'La descripcion admite hasta 200 caracteres.'})
        try:
            movimiento = registrar_movimiento_manual(request.user.empleado, tipo, moneda, monto, descripcion)
        except ReglaCaja as error:
            return _conflicto(error)
        movimiento = MovimientoCaja.objects.select_related('empleado').get(pk=movimiento.pk)
        return Response(MovimientoCajaSerializer(movimiento).data, status=status.HTTP_201_CREATED)


class CajaViewSet(viewsets.ReadOnlyModelViewSet):
    """Historial de cajas, para la auditoria. Admin y Gerente. GET /cajas (filtros: ?estado=Abierta|Cerrada,
    ?fecha=AAAA-MM-DD, la fecha de apertura) y GET /cajas/{id} (con arqueo y movimientos)."""
    roles_lectura = ADMIN_GERENTE

    def get_serializer_class(self):
        return CajaResumenSerializer if self.action == 'list' else CajaDetalleSerializer

    def get_queryset(self):
        queryset = _con_empleados(Caja.objects).order_by('-id')
        if self.action == 'list':
            p = self.request.query_params
            estado = (p.get('estado') or '').strip().lower()
            if estado:
                if estado not in ('abierta', 'cerrada'):
                    raise ValidationError({'estado': "Valores validos: 'Abierta' o 'Cerrada'."})
                queryset = queryset.filter(estado__iexact=estado)
            if p.get('fecha'):
                try:
                    queryset = queryset.filter(fecha_hora_apertura__date=date.fromisoformat(p['fecha']))
                except ValueError:
                    raise ValidationError({'fecha': 'Debe ser una fecha con formato AAAA-MM-DD (ej: 2026-11-06).'})
        return queryset

    def retrieve(self, request, *args, **kwargs):
        caja = self.get_object()
        datos = dict(CajaDetalleSerializer(caja).data)
        movimientos = MovimientoCaja.objects.filter(caja=caja).select_related('empleado').order_by('id')
        datos['movimientos'] = MovimientoCajaSerializer(movimientos, many=True).data
        return Response(datos)
