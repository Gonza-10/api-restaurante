"""Vistas de la cuenta: factura, cobro en efectivo, anulaciones, propinas y la cuenta que ve el cliente."""
from datetime import date, datetime, time

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, ROL_MOZO, SALON
from .caja import ReglaCaja
from .caja_calculos import CajaInvalida, validar_moneda, validar_monto
from .cobros_calculos import CERO, CobroInvalido
from .comprobante import fijar_pedido
from .comprobante_calculos import PedidoInvalido, validar_pedido_de_factura
from .cuenta import (
    ReglaCuenta, anular_factura, anular_pago, armar_cuenta, emitir_factura, pagar_efectivo, pagar_tarjeta, propinas_por_mozo,
)
from .gestor_pago import gestor_publico, leer_plan
from .mercadopago import modo as modo_mercadopago
from .models import Factura, Pago, PedidoCabecera
from .serializers import AccesoClienteSerializer, fecha_iso
from .serializers_cobros import en_texto
from .views import _sesion_cliente


# ---------- ayudas ----------

def _nombre(empleado):
    return f'{empleado.nombre} {empleado.apellido}' if empleado else None


def _cuerpo(request):
    return request.data if isinstance(request.data, dict) else {}


def _campo(campo, error):
    return ValidationError({campo: str(error)})


def _error(error):
    """ReglaCuenta o ReglaCaja -> respuesta con el estado que corresponda."""
    estado = getattr(error, 'estado', 409)
    return Response({'error': error.mensaje, **error.extra}, status=estado)


def _es_mozo(request):
    return request.user.rol == ROL_MOZO


def _sesion_del_usuario(request, sesion_id):
    """La sesion, o None si no existe o es de otro mozo (un mozo solo ve sus mesas)."""
    sesion = PedidoCabecera.objects.select_related('mesa', 'empleado').filter(pk=sesion_id).first()
    if sesion is None or (_es_mozo(request) and sesion.empleado_id != request.user.id):
        return None
    return sesion


def _factura_del_usuario(request, factura_id):
    factura = Factura.objects.select_related('pedido_cabecera__mesa', 'pedido_cabecera__empleado').filter(pk=factura_id).first()
    if factura is None or (_es_mozo(request) and factura.pedido_cabecera.empleado_id != request.user.id):
        return None
    return factura


def _no_existe():
    return Response({'error': 'El recurso solicitado no existe.'}, status=status.HTTP_404_NOT_FOUND)


def pedido_de_factura(datos):
    """La casilla "quiero factura" que llega en el cuerpo de un pago (hito 6). None si no vino (no cambia nada); si vino,
    (quiere, nombre). 400 si esta mal: tildada sin nombre, o el nombre muy largo."""
    try:
        return validar_pedido_de_factura(datos)
    except PedidoInvalido as error:
        raise ValidationError({error.campo: str(error)})


def aplicar_pedido(factura_id, pedido):
    """Guarda la casilla en la factura del pago que se acaba de registrar. Sin casilla en el cuerpo, no hace nada."""
    if pedido is not None:
        fijar_pedido(factura_id, *pedido)


def _pago_json(pago, publico=False):
    datos = {
        'id': pago.id,
        'metodo': pago.metodo_pago.nombre,
        'estado': pago.estado,
        'moneda': pago.moneda,
        'monto_recibido': pago.monto_recibido,
        'cotizacion': pago.cotizacion,
        'monto': pago.monto,                  # lo que descuenta de la cuenta, en pesos
        'propina': pago.monto_propina,        # en pesos
        'vuelto': pago.vuelto,                # siempre en pesos
        'fecha_hora': fecha_iso(pago.fecha_hora),
    }
    if pago.metodo_pago.nombre == 'MercadoPago':
        datos['mp_estado'] = pago.mp_estado
        if pago.estado == 'Pendiente':   # el cliente necesita el link para pagar o retomar el pago
            datos['url_pago'] = pago.mp_url_pago
            datos['expira'] = fecha_iso(pago.fecha_hora_expiracion)
            datos['modo'] = modo_mercadopago()
    if not publico:
        datos['registrado_por'] = _nombre(pago.empleado)
        datos['motivo_anulacion'] = pago.motivo_anulacion
        if pago.metodo_pago.nombre == 'MercadoPago':
            datos['mp_pago_id'] = pago.mp_pago_id
            datos['mp_monto_neto'] = pago.mp_monto_neto
    return datos


def _factura_json(factura):
    return {
        'id': factura.id,
        'estado': factura.estado,
        'fecha_hora_emision': fecha_iso(factura.fecha_hora_emision),
        'fecha_hora_pago': fecha_iso(factura.fecha_hora_pago),
        'total': factura.total,
        'cambio_entregado': factura.cambio_entregado or CERO,
        'cotizaciones': {'USD': factura.cotizacion_usd, 'BRL': factura.cotizacion_brl, 'PYG': factura.cotizacion_pyg},
        # hito 6: el cliente pidio el comprobante PDF; se puede descargar cuando la factura esta Pagada
        'quiere_factura': bool(factura.solicito_ticket),
        'nombre_factura': factura.nombre_factura,
        'comprobante_disponible': bool(factura.solicito_ticket) and factura.estado == 'Pagada',
    }


def cuenta_json(cuenta, publico=False):
    """La cuenta lista para responder. `publico=True` (el cliente): sin nombres del personal ni detalle interno."""
    sesion, factura = cuenta['sesion'], cuenta['factura']
    datos = {
        'sesion': {'id': sesion.id, 'numero_mesa': sesion.mesa.numero, 'estado': sesion.estado},
        'estado_cuenta': cuenta['estado_cuenta'],
        'factura': _factura_json(factura) if factura else None,
        'total': cuenta['total'],
        'saldo': cuenta['saldo'],
        'equivalentes': cuenta['equivalentes'],   # lo que equivale el total en USD, BRL y PYG
        'renglones': cuenta['renglones'],
        'por_comensal': cuenta['por_comensal'],   # informativo: cuanto consumio cada uno
        'pagos': [_pago_json(p, publico) for p in cuenta['pagos']],
        'pago_pendiente': next((_pago_json(p, publico) for p in cuenta['pagos'] if p.estado == 'Pendiente'), None),
        'puede_cobrarse': cuenta['puede_cobrarse'],
        'pedidos_en_cocina': len(cuenta['comandas_en_cocina']),
        'en_sobremesa': cuenta['en_sobremesa'],
        'caja_abierta': cuenta['caja_abierta'],
    }
    datos['plan_pago'] = leer_plan(sesion.id)               # como piensa pagar la mesa (aviso; lo cobra el mozo); lo ven la mesa y el personal
    if not publico:
        datos['sesion']['mozo'] = _nombre(sesion.empleado)
        datos['gestor_pago'] = gestor_publico(sesion.id)   # quien gestiona el pago desde el celular (None si nadie)
    return en_texto(datos)


# ---------- cuenta de una sesion (personal) ----------

class SesionCuentaView(APIView):
    """GET /sesiones-mesa/{id}/cuenta. Mozo (solo sus mesas), Admin y Gerente. Sin factura es una vista previa del consumo
    (total, equivalentes en USD/BRL/PYG y desglose por comensal); con factura, lo congelado al emitirla, los pagos y el saldo.
    `puede_cobrarse` dice si se puede cobrar ahora; `pedidos_en_cocina` cuantos pedidos todavia bloquean el cobro."""
    roles_lectura = SALON

    def get(self, request, pk):
        sesion = _sesion_del_usuario(request, pk)
        if sesion is None:
            return _no_existe()
        return Response(cuenta_json(armar_cuenta(sesion)))


class SesionFacturaView(APIView):
    """POST /sesiones-mesa/{id}/factura. Mozo (solo sus mesas), Admin y Gerente. Emite la factura de la mesa: congela el
    consumo y avisa a la cocina que no entran mas pedidos. Necesita la caja abierta y consumo. Si ya hay una vigente la
    devuelve (200). Para pedir algo mas, el mozo cierra la sesion y abre otra (o un Admin/Gerente anula la factura)."""
    roles_escritura = SALON

    def post(self, request, pk):
        sesion = _sesion_del_usuario(request, pk)
        if sesion is None:
            return _no_existe()
        try:
            factura, creada = emitir_factura(sesion.id, request.user.empleado)
        except (ReglaCuenta, ReglaCaja) as error:
            return _error(error)
        sesion.refresh_from_db()
        return Response(cuenta_json(armar_cuenta(sesion)), status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK)


# ---------- facturas ----------

class FacturaViewSetLista(APIView):
    """GET /facturas. Admin y Gerente. Filtros: ?estado=Emitida|Pagada|Anulada y ?fecha=AAAA-MM-DD (emision)."""
    roles_lectura = ADMIN_GERENTE

    def get(self, request):
        facturas = Factura.objects.select_related('pedido_cabecera__mesa', 'empleado').order_by('-id')
        estado = (request.query_params.get('estado') or '').strip().capitalize()
        if estado:
            if estado not in ('Emitida', 'Pagada', 'Anulada'):
                raise ValidationError({'estado': "Valores validos: 'Emitida', 'Pagada' o 'Anulada'."})
            facturas = facturas.filter(estado=estado)
        fecha = request.query_params.get('fecha')
        if fecha:
            try:
                facturas = facturas.filter(fecha_hora_emision__date=date.fromisoformat(fecha))
            except ValueError:
                raise ValidationError({'fecha': 'Debe ser una fecha con formato AAAA-MM-DD (ej: 2026-11-06).'})
        return Response(en_texto([
            {**_factura_json(f), 'numero_mesa': f.pedido_cabecera.mesa.numero, 'emitida_por': _nombre(f.empleado)}
            for f in facturas[:200]
        ]))


class FacturaDetalleView(APIView):
    """GET /facturas/{id}. Mozo (solo sus mesas), Admin y Gerente: la cuenta completa con renglones, pagos y saldo."""
    roles_lectura = SALON

    def get(self, request, pk):
        factura = _factura_del_usuario(request, pk)
        if factura is None:
            return _no_existe()
        return Response(cuenta_json(armar_cuenta(factura.pedido_cabecera)))


class PagoEfectivoView(APIView):
    """POST /facturas/{id}/pagos/efectivo. Mozo (solo sus mesas), Admin y Gerente. Cobra en efectivo, en UNA moneda:
    {"moneda": "USD", "recibido": 20, "propina": 1500, "monto_cuenta": 20000, "clave": "..."}
    - `recibido`: lo que entrega el cliente, en `moneda` (ARS, USD, BRL o PYG). El sistema lo pasa a pesos con la cotizacion
      vigente y la congela en el pago.
    - `propina` (opcional, en pesos): va solo al mozo de la mesa. Si se deja en otra moneda que la cuenta, es otro cobro.
    - `monto_cuenta` (opcional, en pesos): cuanto de la cuenta paga este cobro; sin indicar, paga todo el saldo que alcance.
    - `clave` (opcional, hasta 36 caracteres): si se reintenta con la misma clave no se cobra dos veces (responde 200 con el
      mismo pago).
    - `quiere_factura` (opcional, hito 6) y `nombre_factura`: la casilla "quiero factura" del cliente. Tildada, el nombre es
      obligatorio. Sin la casilla en el cuerpo no se cambia lo que ya estaba elegido.
    El vuelto es siempre en pesos y lo calcula el sistema. 409 si no hay caja abierta, hay pedidos en preparacion, o falta
    efectivo en pesos para el vuelto."""
    roles_escritura = SALON

    def post(self, request, pk):
        factura = _factura_del_usuario(request, pk)
        if factura is None:
            return _no_existe()
        datos = _cuerpo(request)
        try:
            moneda = validar_moneda(datos.get('moneda'))
        except CajaInvalida as error:
            raise _campo('moneda', error)
        try:
            recibido = validar_monto(datos.get('recibido'), 'recibido', positivo=True)
        except CajaInvalida as error:
            raise _campo('recibido', error)
        try:
            propina = validar_monto(datos.get('propina') if datos.get('propina') not in (None, '') else 0, 'propina')
        except CajaInvalida as error:
            raise _campo('propina', error)
        monto_cuenta = None
        if datos.get('monto_cuenta') not in (None, ''):
            try:
                monto_cuenta = validar_monto(datos.get('monto_cuenta'), 'monto_cuenta')
            except CajaInvalida as error:
                raise _campo('monto_cuenta', error)
        clave = str(datos.get('clave') or '').strip() or None
        if clave and len(clave) > 36:
            raise ValidationError({'clave': 'Admite hasta 36 caracteres.'})
        pedido = pedido_de_factura(datos)   # se valida antes de cobrar: un error de la casilla no debe dejar un cobro hecho

        try:
            pago, creado = pagar_efectivo(factura.id, request.user.empleado, moneda, recibido, propina, monto_cuenta, clave)
        except CobroInvalido as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except (ReglaCuenta, ReglaCaja) as error:
            return _error(error)
        aplicar_pedido(factura.id, pedido)
        pago = Pago.objects.select_related('metodo_pago', 'empleado').get(pk=pago.pk)
        sesion = PedidoCabecera.objects.select_related('mesa', 'empleado').get(pk=factura.pedido_cabecera_id)
        return Response(
            {'pago': en_texto(_pago_json(pago)), 'cuenta': cuenta_json(armar_cuenta(sesion))},
            status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK,
        )


class PagoTarjetaView(APIView):
    """POST /facturas/{id}/pagos/tarjeta. Mozo (solo sus mesas), Admin y Gerente. CONFIRMA un cobro con tarjeta de credito o debito.
    El pago en si es manual: el cliente pide pagar con tarjeta, el mozo le lleva el postnet y, cuando la plata impacto, lo
    confirma aca. {"monto_cuenta": 20000, "clave": "...", "quiere_factura": true, "nombre_factura": "..."} (todo opcional)
    - `monto_cuenta` (pesos): cuanto de la cuenta cubre este cobro; sin indicar, todo el saldo. No hay vuelto.
    - `propina` (pesos, opcional): lo que el cliente dejo ademas de la cuenta; va solo al mozo de la mesa (suma en GET /propinas).
    - `clave` (hasta 36 caracteres): reintentar con la misma clave no cobra dos veces (responde 200 con el mismo pago).
    - `quiere_factura` y `nombre_factura`: igual que en el cobro en efectivo.
    No mueve el efectivo de la caja. Se puede combinar con efectivo o Mercado Pago. 409 si no hay caja abierta o hay pedidos en
    preparacion. Un cobro confirmado por error lo anula un Admin o Gerente (POST /pagos/{id}/anular)."""
    roles_escritura = SALON

    def post(self, request, pk):
        factura = _factura_del_usuario(request, pk)
        if factura is None:
            return _no_existe()
        datos = _cuerpo(request)
        monto_cuenta = None
        if datos.get('monto_cuenta') not in (None, ''):
            try:
                monto_cuenta = validar_monto(datos.get('monto_cuenta'), 'monto_cuenta', positivo=True)
            except CajaInvalida as error:
                raise _campo('monto_cuenta', error)
        propina = None
        if datos.get('propina') not in (None, ''):
            try:
                propina = validar_monto(datos.get('propina'), 'propina')
            except CajaInvalida as error:
                raise _campo('propina', error)
        clave = str(datos.get('clave') or '').strip() or None
        if clave and len(clave) > 36:
            raise ValidationError({'clave': 'Admite hasta 36 caracteres.'})
        pedido = pedido_de_factura(datos)   # se valida antes de cobrar: un error de la casilla no debe dejar un cobro hecho

        try:
            pago, creado = pagar_tarjeta(factura.id, request.user.empleado, monto_cuenta, clave, propina)
        except CobroInvalido as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except (ReglaCuenta, ReglaCaja) as error:
            return _error(error)
        aplicar_pedido(factura.id, pedido)
        pago = Pago.objects.select_related('metodo_pago', 'empleado').get(pk=pago.pk)
        sesion = PedidoCabecera.objects.select_related('mesa', 'empleado').get(pk=factura.pedido_cabecera_id)
        return Response(
            {'pago': en_texto(_pago_json(pago)), 'cuenta': cuenta_json(armar_cuenta(sesion))},
            status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK,
        )


class PagoAnularView(APIView):
    """POST /pagos/{id}/anular. Admin y Gerente. {"motivo": "..."} (obligatorio). Solo pagos aprobados en efectivo o con tarjeta.
    En efectivo devuelve el dinero en la caja abierta (contramovimiento); la tarjeta no movio la caja. Reabre el saldo de la cuenta."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request, pk):
        if not Pago.objects.filter(pk=pk).exists():
            return _no_existe()
        try:
            pago = anular_pago(pk, request.user.empleado, _cuerpo(request).get('motivo'))
        except (ReglaCuenta, ReglaCaja) as error:
            return _error(error)
        pago = Pago.objects.select_related('metodo_pago', 'empleado').get(pk=pago.pk)
        sesion = PedidoCabecera.objects.select_related('mesa', 'empleado').get(pk=pago.factura.pedido_cabecera_id)
        return Response({'pago': en_texto(_pago_json(pago)), 'cuenta': cuenta_json(armar_cuenta(sesion))})


class FacturaAnularView(APIView):
    """POST /facturas/{id}/anular. Admin y Gerente. {"motivo": "..."} (obligatorio). Solo una factura sin pagos aprobados ni
    pendientes (anular antes esos pagos). La mesa vuelve a poder pedir y se puede emitir otra factura."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request, pk):
        if not Factura.objects.filter(pk=pk).exists():
            return _no_existe()
        try:
            factura = anular_factura(pk, request.user.empleado, _cuerpo(request).get('motivo'))
        except (ReglaCuenta, ReglaCaja) as error:
            return _error(error)
        return Response(en_texto(_factura_json(factura)))


# ---------- propinas ----------

def _inicio_del_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min))


class PropinasView(APIView):
    """GET /propinas. Cada mozo ve las suyas; Admin y Gerente ven las de todos (?mozo=id para uno solo). Filtros ?desde y
    ?hasta (AAAA-MM-DD, el dia 'hasta' se incluye). Son las propinas de pagos aprobados, en pesos, por el mozo que atendio la
    mesa."""
    roles_lectura = SALON

    def get(self, request):
        desde = hasta = None
        try:
            if request.query_params.get('desde'):
                desde = _inicio_del_dia(date.fromisoformat(request.query_params['desde']))
            if request.query_params.get('hasta'):
                from datetime import timedelta
                hasta = _inicio_del_dia(date.fromisoformat(request.query_params['hasta']) + timedelta(days=1))
        except ValueError:
            raise ValidationError({'fecha': 'Las fechas deben tener formato AAAA-MM-DD (ej: 2026-11-06).'})
        empleado_id = request.user.id if _es_mozo(request) else request.query_params.get('mozo') or None
        filas = propinas_por_mozo(desde, hasta, empleado_id)
        return Response(en_texto({'por_mozo': filas, 'total': sum((f['propina_total'] for f in filas), CERO)}))


# ---------- el cliente ----------

class CuentaClienteView(APIView):
    """POST /cuenta. Publico, protegido por el PIN de la mesa (como /mesa/historial): {"numero_mesa": 5, "pin": "1234"}.
    El cliente ve el total de su cuenta, lo que equivale en USD, BRL y PYG, cuanto consumio cada comensal, los pagos hechos y
    el saldo. No muestra nombres del personal."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        entrada = AccesoClienteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
        if error is not None:
            return error
        return Response(cuenta_json(armar_cuenta(sesion), publico=True))
