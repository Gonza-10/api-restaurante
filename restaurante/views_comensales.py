"""Comensales, primera ronda y seguridad de la mesa.

Lado del cliente (sin login, protegido por mesa + PIN; son POST para que el PIN viaje en el cuerpo):
  POST /mesa/comensales            el dispositivo escribe su nombre y queda registrado en la mesa
  POST /mesa/comensales/estado     comensales, quienes ya dieron el OK y si la primera ronda salio (se consulta cada pocos segundos)
  POST /mesa/comensales/ok         "ya pedi todo" (OK de la primera ronda de una mesa Grupal)
  POST /mesa/regenerar-pin         un comensal pide un PIN nuevo (avisa al mozo, que se lo da a los que se quedan)
Lado del personal (Mozo: solo sus mesas; Admin y Gerente: todas):
  GET  /sesiones-mesa/{id}/comensales
  POST /sesiones-mesa/{id}/liberar-ronda      libera la primera ronda sin esperar el OK de todos
  POST /sesiones-mesa/{id}/regenerar-pin      cambia el PIN (devuelve el nuevo)
  POST /sesiones-mesa/{id}/pin/visto          el mozo vio el aviso de PIN nuevo
  POST /pedidos/{uuid}/cancelar               cancela una comanda que todavia no empezo a prepararse (devuelve el stock)
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import SALON
from .comensales import (
    cancelar_comanda, comensal_de_sesion, ingresar_comensal, liberar_primera_ronda, marcar_aviso_pin_visto, marcar_ok,
    regenerar_pin, resumen_mesa,
)
from .comensales_calculos import RETIRADO, mensaje_comensal_retirado
from .cuenta import ReglaCuenta
from .serializers import AccesoClienteSerializer
from .serializers_comensales import (
    CancelarComandaSerializer, IngresoComensalSerializer, OkComensalSerializer, RegenerarPinClienteSerializer,
    RegenerarPinMozoSerializer,
)
from .views import _sesion_cliente
from .views_cuenta import _es_mozo, _no_existe, _sesion_del_usuario


def _error(error):
    return Response({'error': error.mensaje, **error.extra}, status=error.estado)


def _datos_comensal(comensal):
    return {'id': comensal.id, 'nombre': comensal.nombre, 'estado': comensal.estado, 'ok': comensal.ok_primera_ronda}


# ---------- cliente ----------

class MesaComensalesView(APIView):
    """POST /mesa/comensales. El dispositivo se presenta con su nombre. El mismo nombre en la misma mesa es la misma persona
    (sin distinguir mayusculas ni acentos): `situacion` = 'nuevo', 'existente' (ya estaba) o 'reactivado' (se habia retirado y
    volvio con el PIN nuevo). El front guarda `comensal.id` y lo manda al pedir. En una mesa Grupal es obligatorio antes de pedir."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None  # publico, protegido por el PIN de la mesa

    def post(self, request):
        entrada = IngresoComensalSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
        if error is not None:
            return error
        try:
            comensal, situacion = ingresar_comensal(sesion.id, entrada.validated_data['nombre'])
        except ReglaCuenta as problema:
            return _error(problema)
        sesion.refresh_from_db()
        return Response(
            {'comensal': _datos_comensal(comensal), 'situacion': situacion, **resumen_mesa(sesion)},
            status=status.HTTP_201_CREATED if situacion == 'nuevo' else status.HTTP_200_OK,
        )


class MesaComensalesEstadoView(APIView):
    """POST /mesa/comensales/estado. Quienes estan en la mesa, quienes dieron el OK y si la primera ronda ya salio a cocina."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        entrada = AccesoClienteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
        if error is not None:
            return error
        return Response(resumen_mesa(sesion))


class MesaOkView(APIView):
    """POST /mesa/comensales/ok. "Ya pedi todo" (tambien vale "nada mas por ahora"). Cuando todos los comensales activos dieron el
    OK, la primera ronda sale junta a cocina (`liberada_ahora`). Con `ok: false` el comensal retira su OK para seguir pidiendo."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        entrada = OkComensalSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
        if error is not None:
            return error
        try:
            sesion, liberada = marcar_ok(sesion.id, entrada.validated_data['id_comensal'], entrada.validated_data['ok'])
        except ReglaCuenta as problema:
            return _error(problema)
        sesion.refresh_from_db()
        return Response({'liberada_ahora': liberada, **resumen_mesa(sesion)})


class MesaRegenerarPinView(APIView):
    """POST /mesa/regenerar-pin. Un comensal pide un PIN nuevo para la mesa (por ejemplo, alguien se fue y sigue pidiendo). La mesa
    sigue siendo la misma sesion: lo pedido y comido queda en la cuenta. `retirados`: ids de quienes se fueron; de cada uno se
    cancelan los pedidos que todavia no se empezaron a preparar (stock devuelto); sin retirados no se cancela nada. El PIN nuevo
    NO se devuelve: le llega al mozo (aviso urgente en la mesa) y se lo da a los que se quedan. Los dispositivos con el PIN viejo
    reciben 403 con codigo 'pin_cambiado'. Se puede volver a pedir recien a los 30 segundos (429, codigo 'espera_pin')."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        entrada = RegenerarPinClienteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        sesion, error = _sesion_cliente(request, datos['numero_mesa'], datos['pin'])
        if error is not None:
            return error
        quien = 'Un comensal'
        if datos.get('id_comensal'):
            comensal = comensal_de_sesion(sesion.id, datos['id_comensal'])
            if comensal is None:
                return Response({'error': 'Ese comensal no está en la mesa.'}, status=status.HTTP_404_NOT_FOUND)
            if comensal.estado == RETIRADO:
                return Response({'error': mensaje_comensal_retirado(), 'codigo': 'comensal_retirado'}, status=status.HTTP_403_FORBIDDEN)
            quien = comensal.nombre
            if comensal.id in datos['retirados']:
                return Response({'error': 'No podés marcarte a vos mismo como retirado.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultado = regenerar_pin(sesion.id, datos['retirados'], quien=quien, respetar_espera=True)
        except ReglaCuenta as problema:
            return _error(problema)
        return Response({
            'mensaje': 'Avisamos al mozo: te va a dar el PIN nuevo. Hasta entonces nadie puede pedir con el PIN anterior.',
            'retirados': resultado['retirados'],
            'comandas_canceladas': resultado['comandas_canceladas'],
        })


# ---------- personal ----------

class SesionComensalesView(APIView):
    """GET /sesiones-mesa/{id}/comensales: modalidad, quienes estan, quienes dieron el OK y si la primera ronda ya salio."""
    roles_lectura = SALON

    def get(self, request, pk):
        sesion = _sesion_del_usuario(request, pk)
        if sesion is None:
            return _no_existe()
        return Response(resumen_mesa(sesion))


class SesionLiberarRondaView(APIView):
    """POST /sesiones-mesa/{id}/liberar-ronda. El mozo libera la primera ronda de una mesa Grupal sin esperar el OK de todos:
    las comandas retenidas pasan a pendiente en la cocina. Devuelve cuantas salieron (0 si ya estaba liberada)."""
    roles_escritura = SALON

    def post(self, request, pk):
        sesion = _sesion_del_usuario(request, pk)
        if sesion is None:
            return _no_existe()
        try:
            liberadas = liberar_primera_ronda(sesion.id)
        except ReglaCuenta as problema:
            return _error(problema)
        sesion.refresh_from_db()
        return Response({'liberadas': liberadas, **resumen_mesa(sesion)})


class SesionRegenerarPinView(APIView):
    """POST /sesiones-mesa/{id}/regenerar-pin. El mozo cambia el PIN de la mesa (mismas reglas que /mesa/regenerar-pin, sin espera
    entre cambios). Devuelve el PIN nuevo, los retirados y las comandas canceladas."""
    roles_escritura = SALON

    def post(self, request, pk):
        sesion = _sesion_del_usuario(request, pk)
        if sesion is None:
            return _no_existe()
        entrada = RegenerarPinMozoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            resultado = regenerar_pin(
                sesion.id, entrada.validated_data['retirados'], quien=f'Mozo {request.user.empleado.nombre}',
                empleado=request.user.empleado)
        except ReglaCuenta as problema:
            return _error(problema)
        # el mozo que lo cambia ya sabe el PIN nuevo: el aviso urgente no hace falta
        marcar_aviso_pin_visto(sesion.id)
        return Response({
            'pin': resultado['pin'], 'retirados': resultado['retirados'], 'comandas_canceladas': resultado['comandas_canceladas'],
        })


class SesionPinVistoView(APIView):
    """POST /sesiones-mesa/{id}/pin/visto. El mozo confirma que vio el aviso de PIN nuevo (`aviso_pin` deja de aparecer en la mesa).
    El PIN vigente se lee en GET /sesiones-mesa/{id}."""
    roles_escritura = SALON

    def post(self, request, pk):
        sesion = _sesion_del_usuario(request, pk)
        if sesion is None:
            return _no_existe()
        marcar_aviso_pin_visto(sesion.id)
        return Response({'mensaje': 'Aviso confirmado.'})


class ComandaCancelarView(APIView):
    """POST /pedidos/{uuid}/cancelar (opcional `motivo`). Cancela una comanda que todavia no empezo a prepararse (retenida o
    pendiente): devuelve el stock y la saca de la cuenta. Con la comanda en proceso, lista o entregada responde 409."""
    roles_escritura = SALON

    def post(self, request, uuid_comanda):
        entrada = CancelarComandaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            comanda = cancelar_comanda(
                uuid_comanda, request.user.empleado, entrada.validated_data.get('motivo'),
                id_empleado_sesion=request.user.id if _es_mozo(request) else None)
        except ReglaCuenta as problema:
            return _error(problema)
        return Response({
            'mensaje': 'Comanda cancelada: el stock se devolvió y no figura en la cuenta.',
            'id_comanda_uuid': str(comanda.id_comanda_uuid), 'estado': comanda.estado,
        })
