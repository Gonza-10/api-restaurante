"""Quien gestiona el pago de la mesa (un solo dispositivo a la vez) y la liberacion por el personal.

Cliente (publicas, protegidas por el PIN de la mesa; `dispositivo` es un identificador que el front guarda en la pestana):
  POST /cuenta/gestor          toma (o renueva) el bloqueo; 409 `gestor_ocupado` si lo tiene otro dispositivo
  POST /cuenta/gestor/estado   consulta quien gestiona sin tomarlo
  POST /cuenta/gestor/soltar   "dejar de gestionar"
Personal:
  POST /sesiones-mesa/{id}/pago/liberar   libera el bloqueo (Mozo de la mesa, Admin, Gerente)
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import SALON
from .gestor_pago import gestor_publico, respuesta_gestor_ocupado, soltar_gestor, tomar_gestor, verificar_gestor
from .plan_pago_calculos import PlanInvalido
from .serializers import AccesoClienteSerializer
from .views import _sesion_cliente
from .views_cuenta import _cuerpo, _no_existe, _sesion_del_usuario


def _sesion_y_dispositivo(request):
    entrada = AccesoClienteSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)
    sesion, error = _sesion_cliente(request, entrada.validated_data['numero_mesa'], entrada.validated_data['pin'])
    return sesion, error, _cuerpo(request)


class CuentaGestorView(APIView):
    """POST /cuenta/gestor. Publico con PIN: {"numero_mesa": 5, "pin": "1234", "dispositivo": "abc12345", "nombre": "Alex"}.
    El dispositivo pasa a gestionar el pago de la mesa (vence a los 10 minutos si no se renueva; la pantalla "Pagar" lo renueva
    mientras esta abierta). 200 si lo tiene este dispositivo; 409 con `codigo: gestor_ocupado` y `gestor.nombre` si lo tiene otro."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        sesion, error, datos = _sesion_y_dispositivo(request)
        if error is not None:
            return error
        try:
            ok, gestor = tomar_gestor(sesion.id, datos.get('dispositivo'), datos.get('nombre'))
        except PlanInvalido as problema:
            return Response({'error': str(problema)}, status=status.HTTP_400_BAD_REQUEST)
        if not ok:
            return respuesta_gestor_ocupado(gestor)
        return Response({'gestiona': True, 'gestor': gestor_publico(sesion.id)})


class CuentaGestorEstadoView(APIView):
    """POST /cuenta/gestor/estado. Publico con PIN. Dice quien gestiona el pago sin tomarlo: {"gestiona": bool, "ocupado": bool, "gestor": {...}|null}."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        sesion, error, datos = _sesion_y_dispositivo(request)
        if error is not None:
            return error
        otro = verificar_gestor(sesion.id, datos.get('dispositivo'))
        gestor = gestor_publico(sesion.id)
        return Response({'gestiona': gestor is not None and otro is None, 'ocupado': otro is not None, 'gestor': gestor})


class CuentaGestorSoltarView(APIView):
    """POST /cuenta/gestor/soltar. Publico con PIN: el dispositivo que gestiona deja de hacerlo y otro puede tomarlo."""
    authentication_classes = []
    roles_lectura = None
    roles_escritura = None

    def post(self, request):
        sesion, error, datos = _sesion_y_dispositivo(request)
        if error is not None:
            return error
        libre = soltar_gestor(sesion.id, dispositivo=str(datos.get('dispositivo') or ''))
        return Response({'liberado': libre})


class SesionPagoLiberarView(APIView):
    """POST /sesiones-mesa/{id}/pago/liberar. El personal libera el bloqueo del pago (por ejemplo, el celular que gestionaba se quedo
    sin bateria). Un Mozo solo en sus mesas."""
    roles_escritura = SALON

    def post(self, request, pk):
        sesion = _sesion_del_usuario(request, pk)
        if sesion is None:
            return _no_existe()
        soltar_gestor(sesion.id, forzar=True)
        return Response({'liberado': True})
