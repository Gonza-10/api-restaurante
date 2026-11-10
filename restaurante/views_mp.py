"""Vistas del cobro con Mercado Pago (hito 4).

Cliente (publicas, protegidas por el PIN de la mesa, como /cuenta):
  POST /cuenta/pagar/mercadopago   empieza el pago y devuelve el link
  POST /cuenta/pagar/estado        consulta como va (confirma con Mercado Pago)
  POST /cuenta/pagar/cancelar      cancela un pago que todavia no se hizo
Personal:
  POST /pagos/{id}/sincronizar     confirma con Mercado Pago ahora (mozo de la mesa, Admin, Gerente)
  POST /pagos/{id}/cancelar        Admin/Gerente, con motivo
  POST /pagos/{id}/simular         solo con MP_MODO=simulado: hace de 'cliente que paga' en las pruebas
"""
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, SALON
from .caja import ReglaCaja
from .caja_calculos import CajaInvalida, validar_monto
from .cobros_calculos import CobroInvalido
from .cuenta import ReglaCuenta, armar_cuenta
from .mercadopago import MercadoPagoError, PasarelaSimulada, modo
from .models import Pago, PedidoCabecera
from .pagos_mp import METODO, cancelar_pago, iniciar_pago, sincronizar_pago
from .redis_client import redis_client
from .serializers import AccesoClienteSerializer
from .serializers_cobros import en_texto
from .gestor_pago import respuesta_gestor_ocupado, verificar_gestor
from .views import _sesion_cliente
from .views_cuenta import _campo, _cuerpo, _error, _es_mozo, _no_existe, _pago_json, aplicar_pedido, cuenta_json, pedido_de_factura

RESULTADOS_SIMULADOS = ('approved', 'rejected', 'in_process')


def _con_cuenta(pago, publico):
    """El pago (releido) junto con la cuenta de su mesa."""
    pago = Pago.objects.select_related('metodo_pago', 'empleado').get(pk=pago.pk)
    sesion = PedidoCabecera.objects.select_related('mesa', 'empleado').get(pk=pago.factura.pedido_cabecera_id)
    return {'pago': en_texto(_pago_json(pago, publico)), 'cuenta': cuenta_json(armar_cuenta(sesion), publico)}


def _hacer(accion, *argumentos):
    """Ejecuta la accion y devuelve (resultado, None) o (None, Response de error)."""
    try:
        return accion(*argumentos), None
    except CobroInvalido as error:
        return None, Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
    except (ReglaCuenta, ReglaCaja) as error:
        return None, _error(error)
    except MercadoPagoError as error:
        return None, Response({'error': f'Mercado Pago: {error}'}, status=status.HTTP_502_BAD_GATEWAY)


def _pago_de_la_sesion(sesion, datos):
    """El pago de Mercado Pago de ESTA sesion (el PIN solo da acceso a la mesa propia). None si no corresponde."""
    try:
        pago_id = int(datos.get('pago'))
    except (TypeError, ValueError):
        raise ValidationError({'pago': 'Falta el id del pago (numero entero).'})
    return Pago.objects.select_related('metodo_pago').filter(
        pk=pago_id, factura__pedido_cabecera=sesion, metodo_pago__nombre=METODO).first()


def _sesion_y_datos(request):
    entrada = AccesoClienteSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)
    sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
    return sesion, error, _cuerpo(request)


# ---------- el cliente ----------

class PagarMercadoPagoClienteView(APIView):
    """POST /cuenta/pagar/mercadopago. Publico con PIN: {"numero_mesa": 5, "pin": "1234", "monto_cuenta": 8000,
    "propina": 800, "clave": "...", "quiere_factura": true, "nombre_factura": "David"}. `monto_cuenta` (opcional, pesos):
    cuanto de la cuenta paga ahora (sin indicar, todo el saldo). `propina` (opcional, pesos). `clave` (opcional): reintentar
    con la misma no crea otro pago. `quiere_factura` / `nombre_factura` (opcional, hito 6): la casilla "quiero factura" que el
    cliente marca antes de ir a Mercado Pago; tildada, el nombre es obligatorio (400 si falta). Sin la casilla no se cambia
    lo ya elegido.
    Si la cuenta no tenia factura se emite en este momento (la mesa deja de recibir pedidos). Responde 201 con
    `pago.url_pago` (a donde mandar al cliente) o 200 si ya habia un pago pendiente (se devuelve el mismo link).
    409: sin caja abierta, pedidos en preparacion, cuenta ya cubierta. 502: no se pudo crear el link."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        sesion, error, datos = _sesion_y_datos(request)
        if error is not None:
            return error
        ocupado = verificar_gestor(sesion.id, datos.get('dispositivo'))   # solo gestiona el pago un dispositivo a la vez
        if ocupado is not None:
            return respuesta_gestor_ocupado(ocupado)
        monto_cuenta = None
        if datos.get('monto_cuenta') not in (None, ''):
            try:
                monto_cuenta = validar_monto(datos.get('monto_cuenta'), 'monto_cuenta', positivo=True)
            except CajaInvalida as e:
                raise _campo('monto_cuenta', e)
        try:
            propina = validar_monto(datos.get('propina') if datos.get('propina') not in (None, '') else 0, 'propina')
        except CajaInvalida as e:
            raise _campo('propina', e)
        clave = str(datos.get('clave') or '').strip() or None
        if clave and len(clave) > 36:
            raise ValidationError({'clave': 'Admite hasta 36 caracteres.'})
        pedido = pedido_de_factura(datos)   # antes de crear el link: un error de la casilla no debe dejar un pago pendiente

        resultado, error = _hacer(iniciar_pago, sesion, monto_cuenta, propina, clave)
        if error is not None:
            return error
        pago, creado = resultado
        aplicar_pedido(pago.factura_id, pedido)
        return Response(_con_cuenta(pago, True), status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK)


class PagarEstadoClienteView(APIView):
    """POST /cuenta/pagar/estado. Publico con PIN: {"numero_mesa": 5, "pin": "1234", "pago": 12}. Confirma con Mercado Pago y
    devuelve el pago y la cuenta. Si Mercado Pago no responde, devuelve lo ultimo que se sabe con un `aviso`."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        sesion, error, datos = _sesion_y_datos(request)
        if error is not None:
            return error
        pago = _pago_de_la_sesion(sesion, datos)
        if pago is None:
            return _no_existe()
        aviso = None
        try:
            pago = sincronizar_pago(pago.id)
        except ReglaCuenta as e:
            if e.estado != 502:
                return _error(e)
            aviso = e.mensaje   # el cliente sigue viendo lo ultimo conocido; vuelve a consultar en unos segundos
        cuerpo = _con_cuenta(pago, True)
        if aviso:
            cuerpo['aviso'] = aviso
        return Response(cuerpo)


class PagarCancelarClienteView(APIView):
    """POST /cuenta/pagar/cancelar. Publico con PIN: {"numero_mesa": 5, "pin": "1234", "pago": 12}. Cancela un pago pendiente
    solo si Mercado Pago confirma que no se pago (y deja vencido el link). Si hay un pago en proceso responde 409."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        sesion, error, datos = _sesion_y_datos(request)
        if error is not None:
            return error
        ocupado = verificar_gestor(sesion.id, datos.get('dispositivo'))
        if ocupado is not None:
            return respuesta_gestor_ocupado(ocupado)
        pago = _pago_de_la_sesion(sesion, datos)
        if pago is None:
            return _no_existe()
        pago, error = _hacer(cancelar_pago, pago.id, None, 'Cancelado por el cliente')
        if error is not None:
            return error
        return Response(_con_cuenta(pago, True))


# ---------- el personal ----------

def _pago_del_usuario(request, pk):
    pago = Pago.objects.select_related('metodo_pago', 'factura__pedido_cabecera').filter(pk=pk).first()
    if pago is None or pago.metodo_pago.nombre != METODO:
        return None
    if _es_mozo(request) and pago.factura.pedido_cabecera.empleado_id != request.user.id:
        return None
    return pago


class PagoSincronizarView(APIView):
    """POST /pagos/{id}/sincronizar. Mozo (solo sus mesas), Admin y Gerente. Pregunta a Mercado Pago ahora (el worker lo hace
    solo cada pocos segundos) y devuelve el pago y la cuenta. 502 si Mercado Pago no responde."""
    roles_escritura = SALON

    def post(self, request, pk):
        pago = _pago_del_usuario(request, pk)
        if pago is None:
            return _no_existe()
        pago, error = _hacer(sincronizar_pago, pago.id)
        if error is not None:
            return error
        return Response(_con_cuenta(pago, False))


class PagoCancelarView(APIView):
    """POST /pagos/{id}/cancelar. Admin y Gerente: {"motivo": "..."} (obligatorio). Cancela un pago de Mercado Pago pendiente
    solo si Mercado Pago confirma que no se pago. Libera el saldo de la cuenta."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request, pk):
        pago = _pago_del_usuario(request, pk)
        if pago is None:
            return _no_existe()
        motivo = str(_cuerpo(request).get('motivo') or '').strip()
        if not motivo:
            return Response({'error': 'Indicar el motivo de la cancelacion.'}, status=status.HTTP_400_BAD_REQUEST)
        pago, error = _hacer(cancelar_pago, pago.id, request.user.empleado, motivo)
        if error is not None:
            return error
        return Response(_con_cuenta(pago, False))


class PagoSimularView(APIView):
    """POST /pagos/{id}/simular. Admin y Gerente, SOLO con MP_MODO=simulado (si no, 404): hace de 'cliente que paga el link'.
    {"resultado": "approved" | "rejected" | "in_process", "monto": 8800 (opcional: para probar un monto distinto)}.
    Despues hay que sincronizar (o esperar al worker) para que el sistema lo vea, igual que con Mercado Pago real."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request, pk):
        if modo() != 'simulado':
            return _no_existe()
        pago = _pago_del_usuario(request, pk)
        if pago is None:
            return _no_existe()
        datos = _cuerpo(request)
        resultado = str(datos.get('resultado') or 'approved').strip()
        if resultado not in RESULTADOS_SIMULADOS:
            raise ValidationError({'resultado': f"Valores validos: {', '.join(RESULTADOS_SIMULADOS)}."})
        monto = pago.monto + pago.monto_propina
        if datos.get('monto') not in (None, ''):
            try:
                monto = validar_monto(datos.get('monto'), 'monto', positivo=True)
            except CajaInvalida as e:
                raise _campo('monto', e)
        simulado = PasarelaSimulada(redis_client).simular(pago.referencia_externa, resultado, monto)
        return Response({'simulado': en_texto({'id': simulado['id'], 'estado': simulado['estado'], 'monto': monto})},
                        status=status.HTTP_201_CREATED)
