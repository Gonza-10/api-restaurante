"""Conexion con Mercado Pago (Checkout Pro con preferencias) y su version simulada.

Hay tres modos, segun `MP_MODO` en el `.env`:
- `simulado` (por defecto): no sale a internet. El link de pago es falso y un Admin/Gerente "paga" con
  POST /pagos/{id}/simular. Sirve para probar todo el circuito sin cuenta de Mercado Pago.
- `prueba`: Mercado Pago real con las credenciales de PRUEBA (`MP_ACCESS_TOKEN`); nadie paga de verdad.
- `produccion`: Mercado Pago real, plata real.

Solo libreria estandar (urllib), igual que la cotizacion. Se verifica el certificado TLS. El token viaja siempre por el
header `Authorization` y nunca se escribe en mensajes de error ni en logs.

Las dos pasarelas tienen la misma interfaz:
    crear_preferencia(referencia, titulo, monto, propina, expira_en)  -> {'id', 'url'}
    buscar_pagos(referencia)                                           -> [pago, ...] (normalizados, ver `normalizar_pago`)
    expirar_preferencia(preferencia_id)                                -> True cuando Mercado Pago confirmo que ya no se puede pagar
"""
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from decouple import config
from django.utils import timezone

MODOS = ('simulado', 'prueba', 'produccion')
TIMEOUT_SEGUNDOS = 12
ESTADOS_EN_CURSO = ('pending', 'in_process', 'authorized', 'in_mediation')   # el cliente ya pago, falta la acreditacion


class MercadoPagoError(Exception):
    """No se pudo hablar con Mercado Pago (sin red, error del servidor, credenciales invalidas, respuesta rara)."""


def modo():
    valor = (config('MP_MODO', default='simulado') or 'simulado').strip().lower()
    return valor if valor in MODOS else 'simulado'


def minutos_de_expiracion():
    try:
        return max(5, int(config('MP_EXPIRACION_MIN', default=30)))
    except (TypeError, ValueError):
        return 30


# ---------- lectura de lo que informa Mercado Pago ----------

def _decimal(valor):
    try:
        return Decimal(str(valor)) if valor is not None else None
    except (InvalidOperation, ValueError):
        return None


def normalizar_pago(crudo):
    """Un pago de la respuesta de /v1/payments/search como lo usa el sistema:
    {'id', 'estado', 'detalle', 'monto' (Decimal bruto cobrado), 'neto' (Decimal o None)}."""
    detalles = crudo.get('transaction_details') or {}
    return {
        'id': str(crudo.get('id')),
        'estado': str(crudo.get('status') or ''),
        'detalle': str(crudo.get('status_detail') or ''),
        'monto': _decimal(crudo.get('transaction_amount')),
        'neto': _decimal(detalles.get('net_received_amount')),
    }


def resolver_estado(pagos):
    """Que pasa con un cobro segun los pagos que tiene en Mercado Pago. Un cliente puede intentar varias veces con el mismo
    link, por eso un rechazo NO termina el cobro. Devuelve (veredicto, pago):
    - 'aprobado': hay un pago `approved` (pago = el primero).
    - 'en_curso': hay uno pendiente de acreditacion (no se puede vencer ni cancelar el cobro todavia).
    - 'rechazado': solo hay intentos rechazados (el link sigue valido hasta que venza).
    - 'sin_pagos': nadie pago todavia."""
    for p in pagos:
        if p['estado'] == 'approved':
            return 'aprobado', p
    for p in pagos:
        if p['estado'] in ESTADOS_EN_CURSO:
            return 'en_curso', p
    if pagos:
        return 'rechazado', pagos[0]
    return 'sin_pagos', None


# ---------- Mercado Pago real ----------

def _iso(fecha):
    """Fecha con zona horaria en el formato que pide Mercado Pago (2026-11-07T04:00:00.000-03:00)."""
    return timezone.localtime(fecha).isoformat(timespec='milliseconds')


class PasarelaMercadoPago:
    def __init__(self):
        self.url = config('MP_API_URL', default='https://api.mercadopago.com').rstrip('/')
        self.token = config('MP_ACCESS_TOKEN', default='').strip()
        self.front = config('MP_FRONT_URL', default='http://localhost:8080').rstrip('/')
        self.notificacion = config('MP_NOTIFICATION_URL', default='').strip()

    def _pedir(self, metodo, ruta, cuerpo=None):
        if not self.token:
            raise MercadoPagoError('Falta MP_ACCESS_TOKEN en el .env: no se puede hablar con Mercado Pago.')
        datos = json.dumps(cuerpo).encode('utf-8') if cuerpo is not None else None
        cabeceras = {'Authorization': f'Bearer {self.token}', 'Accept': 'application/json', 'User-Agent': 'SavageGrill/1.0'}
        if cuerpo is not None:
            cabeceras['Content-Type'] = 'application/json'
        if metodo == 'POST':
            cabeceras['X-Idempotency-Key'] = str(uuid.uuid4())
        pedido = urllib.request.Request(self.url + ruta, data=datos, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS) as respuesta:
                return json.loads(respuesta.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise MercadoPagoError('Mercado Pago rechazo las credenciales (revisar MP_ACCESS_TOKEN).') from error
            try:
                causa = json.loads(error.read().decode('utf-8')).get('message') or ''
            except (ValueError, OSError, AttributeError):
                causa = ''
            raise MercadoPagoError(f'Mercado Pago respondio con error {error.code}. {causa}'.strip()) from error
        except (urllib.error.URLError, OSError, ValueError) as error:   # sin red, tiempo agotado, certificado, JSON roto
            raise MercadoPagoError(f'No se pudo conectar con Mercado Pago: {error}') from error

    def crear_preferencia(self, referencia, titulo, monto, propina, expira_en):
        items = [{'id': 'cuenta', 'title': titulo, 'quantity': 1, 'currency_id': 'ARS', 'unit_price': float(monto)}]
        if propina > 0:
            items.append({'id': 'propina', 'title': 'Propina', 'quantity': 1, 'currency_id': 'ARS', 'unit_price': float(propina)})
        cuerpo = {
            'items': items,
            'external_reference': referencia,
            'back_urls': {k: f'{self.front}/?mp={k}&ref={referencia}' for k in ('success', 'failure', 'pending')},
            'statement_descriptor': 'SAVAGE GRILL',
            'expires': True,
            'expiration_date_from': _iso(timezone.now()),
            'expiration_date_to': _iso(expira_en),
        }
        if self.notificacion:
            cuerpo['notification_url'] = self.notificacion
        respuesta = self._pedir('POST', '/checkout/preferences', cuerpo)
        # con el Access Token de PRUEBA, init_point ya lleva al checkout de prueba (sandbox_init_point quedo en desuso)
        url = respuesta.get('init_point')
        if not respuesta.get('id') or not url:
            raise MercadoPagoError('Mercado Pago no devolvio el link de pago.')
        return {'id': str(respuesta['id']), 'url': url}

    def buscar_pagos(self, referencia):
        ruta = f'/v1/payments/search?external_reference={urllib.parse.quote(referencia)}&sort=date_created&criteria=desc'
        respuesta = self._pedir('GET', ruta)
        return [normalizar_pago(p) for p in (respuesta.get('results') or [])]

    def expirar_preferencia(self, preferencia_id):
        """Vence el link ahora. Devuelve True solo si Mercado Pago confirma que quedo vencido."""
        ahora = timezone.now()
        respuesta = self._pedir('PUT', f'/checkout/preferences/{urllib.parse.quote(preferencia_id)}',
                                {'expires': True, 'expiration_date_to': _iso(ahora)})
        return bool(respuesta.get('expires'))


# ---------- simulada (sin internet) ----------

class PasarelaSimulada:
    """Guarda en Redis lo que haria Mercado Pago. `simular` es el 'pago' del cliente."""
    EXPIRA_SEG = 24 * 3600

    def __init__(self, redis):
        self.redis = redis
        self.front = config('MP_FRONT_URL', default='http://localhost:8080').rstrip('/')

    def _clave(self, referencia):
        return f'mp:sim:pagos:{referencia}'

    def _leer(self, referencia):
        crudo = self.redis.get(self._clave(referencia))
        return json.loads(crudo) if crudo else []

    def crear_preferencia(self, referencia, titulo, monto, propina, expira_en):
        return {'id': f'SIM-{referencia}', 'url': f'{self.front}/pago-simulado?ref={referencia}'}

    def buscar_pagos(self, referencia):
        return [
            {'id': p['id'], 'estado': p['estado'], 'detalle': p['detalle'], 'monto': Decimal(p['monto']),
             'neto': Decimal(p['neto']) if p.get('neto') else None}
            for p in self._leer(referencia)
        ]

    def expirar_preferencia(self, preferencia_id):
        return True

    def simular(self, referencia, estado, monto):
        """El cliente 'paga' el link: estado approved | rejected | in_process. Devuelve el pago simulado."""
        pagos = self._leer(referencia)
        pago = {
            'id': f'{referencia}-{len(pagos) + 1}', 'estado': estado, 'detalle': 'simulado',
            'monto': str(monto), 'neto': str((Decimal(monto) * Decimal('0.9')).quantize(Decimal('0.01'))),
        }
        pagos.insert(0, pago)
        self.redis.set(self._clave(referencia), json.dumps(pagos), ex=self.EXPIRA_SEG)
        return pago


def pasarela():
    """La pasarela del modo configurado."""
    if modo() == 'simulado':
        from .redis_client import redis_client
        return PasarelaSimulada(redis_client)
    return PasarelaMercadoPago()


def vencimiento(desde=None):
    return (desde or timezone.now()) + timedelta(minutes=minutos_de_expiracion())
