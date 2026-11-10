"""Quien gestiona el pago de una mesa y el plan de pago que armo, guardados en Redis (no hay tablas nuevas).

- Gestor: de todos los dispositivos de la mesa, uno solo gestiona el pago a la vez; los demas ven que esta ocupado. El
  bloqueo vence solo a los 10 minutos sin actividad (la pantalla "Pagar" lo renueva mientras esta abierta), el que gestiona
  puede soltarlo y el mozo (o un Admin/Gerente) puede liberarlo.
- Plan: como piensa pagar la mesa (ver plan_pago_calculos.py). Es un aviso para el mozo y la caja; dura 6 horas.
"""
import json

from rest_framework import status
from rest_framework.response import Response

from .plan_pago_calculos import PlanInvalido, validar_dispositivo
from .redis_client import redis_client

TTL_GESTOR_SEGUNDOS = 600
TTL_PLAN_SEGUNDOS = 6 * 3600


def _clave_gestor(sesion_id):
    return f'mesa:gestor_pago:{sesion_id}'


def _clave_plan(sesion_id):
    return f'mesa:plan_pago:{sesion_id}'


def _leer(clave):
    texto = redis_client.get(clave)
    if not texto:
        return None
    try:
        return json.loads(texto)
    except ValueError:
        return None


def leer_gestor(sesion_id):
    """{'dispositivo', 'nombre'} de quien gestiona el pago, o None si esta libre."""
    return _leer(_clave_gestor(sesion_id))


def gestor_publico(sesion_id):
    """Lo que ven el personal y los demas dispositivos: quien gestiona (sin el identificador del dispositivo) y cuanto le queda."""
    gestor = leer_gestor(sesion_id)
    if gestor is None:
        return None
    restante = redis_client.ttl(_clave_gestor(sesion_id))
    return {'nombre': gestor.get('nombre') or 'Otro comensal', 'vence_en_segundos': restante if restante and restante > 0 else 0}


def tomar_gestor(sesion_id, dispositivo, nombre=None):
    """Toma (o renueva) el bloqueo. Devuelve (True, None) si el dispositivo gestiona, o (False, gestor_publico) si lo tiene otro."""
    dispositivo = validar_dispositivo(dispositivo)
    nombre = (nombre or '').strip()[:50] or None
    valor = json.dumps({'dispositivo': dispositivo, 'nombre': nombre})
    if redis_client.set(_clave_gestor(sesion_id), valor, nx=True, ex=TTL_GESTOR_SEGUNDOS):
        return True, None
    actual = leer_gestor(sesion_id)
    if actual is None or actual.get('dispositivo') == dispositivo:
        redis_client.set(_clave_gestor(sesion_id), valor, ex=TTL_GESTOR_SEGUNDOS)
        return True, None
    return False, gestor_publico(sesion_id)


def soltar_gestor(sesion_id, dispositivo=None, forzar=False):
    """Libera el bloqueo (el que gestiona, o el personal con `forzar`). Devuelve True si quedo libre."""
    actual = leer_gestor(sesion_id)
    if actual is None:
        return True
    if forzar or (dispositivo and actual.get('dispositivo') == dispositivo):
        redis_client.delete(_clave_gestor(sesion_id))
        return True
    return False


def verificar_gestor(sesion_id, dispositivo):
    """None si el dispositivo puede gestionar el pago (lo tiene o nadie lo tiene); si lo tiene otro, su gestor_publico."""
    actual = leer_gestor(sesion_id)
    if actual is None:
        return None
    try:
        dispositivo = validar_dispositivo(dispositivo)
    except PlanInvalido:
        return gestor_publico(sesion_id)
    return None if actual.get('dispositivo') == dispositivo else gestor_publico(sesion_id)


def respuesta_gestor_ocupado(gestor):
    nombre = (gestor or {}).get('nombre') or 'Otro comensal'
    return Response(
        {'error': f'{nombre} está gestionando el pago de la mesa. Esperá a que termine o pedile al mozo que lo libere.',
         'codigo': 'gestor_ocupado', 'gestor': gestor},
        status=status.HTTP_409_CONFLICT)


def guardar_plan(sesion_id, plan, por=None):
    plan = dict(plan, por=(por or '').strip()[:50] or None)
    redis_client.set(_clave_plan(sesion_id), json.dumps(plan), ex=TTL_PLAN_SEGUNDOS)
    return plan


def leer_plan(sesion_id):
    return _leer(_clave_plan(sesion_id))


def borrar_plan(sesion_id):
    redis_client.delete(_clave_plan(sesion_id))
