"""Plan de pago que arma el cliente en la pantalla "Pagar" (reglas puras, sin Django ni Redis, para poder probarlas solas).

El plan es un AVISO para el mozo y la caja: dice como piensa pagar la mesa (modo y partes por medio de pago). No cobra nada:
la parte de Mercado Pago se cobra sola por su propio flujo; las de efectivo y tarjeta las cobra y registra el mozo (siempre
controladas por el mozo y la caja, el plan solo orienta).
"""
from decimal import Decimal

from .caja_calculos import CajaInvalida, validar_monto

MODOS = ('todo', 'consumo', 'partes_iguales')          # toda la cuenta junta / cada uno lo que consumio / en partes iguales
METODOS = {'efectivo': 'Efectivo', 'tarjeta': 'Tarjeta', 'mercadopago': 'MercadoPago'}
MAX_PARTES = 6
DEVICE_LARGO = (8, 64)


class PlanInvalido(ValueError):
    """El plan de pago no sirve (el mensaje se muestra tal cual)."""


def validar_dispositivo(valor):
    """Identificador del dispositivo que gestiona el pago: texto de 8 a 64 caracteres (letras, numeros, guion y guion bajo)."""
    if not isinstance(valor, str):
        raise PlanInvalido('Falta el identificador del dispositivo.')
    limpio = valor.strip()
    minimo, maximo = DEVICE_LARGO
    if not (minimo <= len(limpio) <= maximo) or not all(c.isalnum() or c in '-_' for c in limpio):
        raise PlanInvalido('El identificador del dispositivo no es valido.')
    return limpio


def validar_plan(modo, partes):
    """Normaliza el plan. `partes`: lista de {"metodo": "efectivo"|"tarjeta"|"mercadopago", "monto": pesos, "propina": pesos (opcional)}.
    Devuelve {"modo": ..., "partes": [{"metodo": 'Efectivo', "monto": '1000.00', "propina": '100.00'}]}. Lanza PlanInvalido."""
    modo = 'todo' if modo in (None, '') else modo
    if modo not in MODOS:
        raise PlanInvalido(f'El modo de pago debe ser uno de: {", ".join(MODOS)}.')
    if not isinstance(partes, list) or not partes:
        raise PlanInvalido('El plan de pago necesita al menos una parte.')
    if len(partes) > MAX_PARTES:
        raise PlanInvalido(f'El plan admite hasta {MAX_PARTES} partes.')
    vistos = set()
    normalizadas = []
    for parte in partes:
        if not isinstance(parte, dict):
            raise PlanInvalido('Cada parte del plan debe indicar medio y monto.')
        clave = ''.join(c for c in str(parte.get('metodo', '')).lower() if c.isalnum())
        if clave not in METODOS:
            raise PlanInvalido('El medio de cada parte debe ser efectivo, tarjeta o mercadopago.')
        if clave in vistos:
            raise PlanInvalido('Cada medio de pago puede aparecer una sola vez en el plan.')
        vistos.add(clave)
        try:
            monto = validar_monto(parte.get('monto'), 'monto', positivo=True)
            propina = validar_monto(parte.get('propina') if parte.get('propina') not in (None, '') else 0, 'propina')
        except CajaInvalida as error:
            raise PlanInvalido(str(error))
        normalizadas.append({'metodo': METODOS[clave], 'monto': str(monto), 'propina': str(propina)})
    return {'modo': modo, 'partes': normalizadas}


def partes_al_aire(plan):
    """Las partes que cobra el mozo (efectivo y tarjeta): lo que el aviso le muestra. Mercado Pago se cobra solo."""
    return [p for p in (plan or {}).get('partes', []) if p['metodo'] in ('Efectivo', 'Tarjeta')]


def resumen_texto(plan):
    """Una linea para el mozo: 'Efectivo $15000.00 + Tarjeta $5000.00 + Mercado Pago $8000.00'."""
    nombres = {'Efectivo': 'Efectivo', 'Tarjeta': 'Tarjeta', 'MercadoPago': 'Mercado Pago'}
    partes = (plan or {}).get('partes', [])
    return ' + '.join(f"{nombres[p['metodo']]} ${Decimal(p['monto'])}" for p in partes)
