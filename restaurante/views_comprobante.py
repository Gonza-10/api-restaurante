"""Vistas del comprobante PDF de la factura (hito 6).

Cliente (publicas, protegidas por el PIN de la mesa; el PIN va en el cuerpo, nunca en la URL):
  POST /cuenta/factura        tilda o destilda "quiero factura" y el nombre (si todavia no hay factura, se manda en el pago)
  POST /cuenta/comprobante    descarga el PDF (cuando la cuenta esta Pagada)
Personal (mozo solo de sus mesas, Admin y Gerente):
  GET   /facturas/{id}/comprobante   descarga el PDF
  PATCH /facturas/{id}/comprobante   tilda o destilda "quiero factura" y el nombre
"""
import io

from django.http import FileResponse
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import SALON
from .comprobante import comprobante_disponible, fijar_pedido, generar
from .cuenta import ReglaCuenta, factura_vigente
from .serializers import AccesoClienteSerializer
from .gestor_pago import respuesta_gestor_ocupado, verificar_gestor
from .views import _sesion_cliente
from .views_cuenta import _cuerpo, _error, _factura_del_usuario, _no_existe, pedido_de_factura


def estado_del_pedido(factura):
    """Lo que el front necesita para mostrar la casilla y el boton de descarga."""
    try:
        comprobante_disponible(factura)
        descargable, motivo = True, None
    except ReglaCuenta as error:
        descargable, motivo = False, error.mensaje
    return {
        'factura': factura.id, 'estado': factura.estado, 'quiere_factura': bool(factura.solicito_ticket),
        'nombre_factura': factura.nombre_factura, 'descargable': descargable, 'motivo': motivo,
    }


def respuesta_pdf(factura, descargar=False):
    """El PDF listo para el navegador. El nombre del archivo viaja en el encabezado (con acentos incluidos)."""
    contenido, nombre = generar(factura)
    return FileResponse(io.BytesIO(contenido), content_type='application/pdf', as_attachment=descargar, filename=nombre)


def guardar_pedido(factura, pedido):
    """Aplica la casilla a la factura, o devuelve una respuesta de error. Devuelve (factura, None) o (None, Response)."""
    try:
        return fijar_pedido(factura.id, *pedido), None
    except ReglaCuenta as error:
        return None, _error(error)


# ---------- el cliente ----------

class CuentaFacturaClienteView(APIView):
    """POST /cuenta/factura. Publico con PIN: {"numero_mesa": 5, "pin": "1234", "quiere_factura": true, "nombre_factura": "David"}.
    Sirve para pedir (o dejar de pedir) la factura una vez emitida. Lo normal es mandar los mismos dos campos al pagar
    (`/cuenta/pagar/mercadopago`), que es cuando se emite la factura. 409 si todavia no hay factura emitida."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        entrada = AccesoClienteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
        if error is not None:
            return error
        cuerpo = _cuerpo(request)
        ocupado = verificar_gestor(sesion.id, cuerpo.get('dispositivo'))   # solo quien gestiona el pago puede cargar la factura
        if ocupado is not None:
            return respuesta_gestor_ocupado(ocupado)
        pedido = pedido_de_factura(cuerpo)
        if pedido is None:
            raise ValidationError({'quiere_factura': 'Indicar verdadero o falso.'})
        factura = factura_vigente(sesion)
        if factura is None:
            return _error(ReglaCuenta('Todavia no hay factura emitida: indicar "quiere_factura" y "nombre_factura" al empezar a pagar.'))
        factura, error = guardar_pedido(factura, pedido)
        return error or Response(estado_del_pedido(factura))


class CuentaComprobanteClienteView(APIView):
    """POST /cuenta/comprobante. Publico con PIN: {"numero_mesa": 5, "pin": "1234"}. Devuelve el PDF de la factura (el nombre
    del archivo viene en `Content-Disposition`). 409 si no se pidio la factura o la cuenta todavia no esta pagada. El PIN va en
    el cuerpo y no en la URL para que no quede en registros ni en el historial del navegador: el front lo pide con fetch y
    descarga el resultado como archivo."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        entrada = AccesoClienteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
        if error is not None:
            return error
        factura = factura_vigente(sesion)
        if factura is None:
            return _error(ReglaCuenta('Todavia no hay factura emitida.'))
        try:
            return respuesta_pdf(factura, descargar=str(_cuerpo(request).get('descargar')).lower() in ('true', '1'))
        except ReglaCuenta as e:
            return _error(e)


# ---------- el personal ----------

class FacturaComprobanteView(APIView):
    """GET /facturas/{id}/comprobante (?descargar=1 para forzar la descarga) y PATCH /facturas/{id}/comprobante con
    {"quiere_factura": true, "nombre_factura": "David"}. Mozo (solo sus mesas), Admin y Gerente. El PDF solo existe si la
    factura se pidio y esta Pagada; si no, 409 con el motivo."""
    roles_lectura = SALON
    roles_escritura = SALON

    def get(self, request, pk):
        factura = _factura_del_usuario(request, pk)
        if factura is None:
            return _no_existe()
        try:
            return respuesta_pdf(factura, descargar=request.query_params.get('descargar') in ('1', 'true'))
        except ReglaCuenta as error:
            return _error(error)

    def patch(self, request, pk):
        factura = _factura_del_usuario(request, pk)
        if factura is None:
            return _no_existe()
        pedido = pedido_de_factura(_cuerpo(request))
        if pedido is None:
            raise ValidationError({'quiere_factura': 'Indicar verdadero o falso.'})
        factura, error = guardar_pedido(factura, pedido)
        return error or Response(estado_del_pedido(factura))
