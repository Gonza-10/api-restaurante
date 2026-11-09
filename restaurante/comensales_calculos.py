"""Reglas puras de comensales y de seguridad de la mesa (sin Django ni base de datos, para poder probarlas solas).

- Modalidad: Familiar (todos agregan al pedido, la cuenta va a nombre de uno; sin espera) o Grupal (cada dispositivo pone su
  nombre y la PRIMERA ronda sale a cocina cuando todos dieron el OK o cuando el mozo la libera).
- Una comanda retenida ya descuento su stock, pero la cocina no la ve hasta que sale la primera ronda.
- Quien se va de la mesa: sus comandas que todavia no empezaron a prepararse (`retenida` o `pendiente`) se cancelan y se
  devuelve el stock; las que estan `proceso`, `listo` o ya entregadas se quedan en la cuenta de la mesa.
"""
import math
import re
import unicodedata
from decimal import Decimal

FAMILIAR = 'Familiar'
GRUPAL = 'Grupal'
MODALIDADES = (FAMILIAR, GRUPAL)

ACTIVO = 'Activo'
RETIRADO = 'Retirado'

# estados de una comanda aceptada mientras vive en Redis (una comanda entregada ya no esta ahi)
RETENIDA = 'retenida'
PENDIENTE = 'pendiente'
PROCESO = 'proceso'
LISTO = 'listo'
ENTREGADO = 'entregado'
ESTADOS_ACTIVOS = (RETENIDA, PENDIENTE, PROCESO, LISTO)       # la comanda sigue sin entregarse: la mesa no se puede cerrar
ESTADOS_CANCELABLES = (RETENIDA, PENDIENTE)                    # todavia no empezaron a prepararse

NOMBRE_MAXIMO = 50
ESPERA_REGENERAR_PIN_SEGUNDOS = 30   # entre dos pedidos de PIN nuevo hechos desde un dispositivo de la mesa


def modalidad_valida(texto):
    """Devuelve 'Familiar' o 'Grupal' (sin importar mayusculas ni espacios) o None si no es una modalidad."""
    limpio = (texto or '').strip().casefold()
    for modalidad in MODALIDADES:
        if limpio == modalidad.casefold():
            return modalidad
    return None


def limpiar_nombre(texto):
    """Nombre de un comensal sin espacios de mas, o ValueError con el motivo."""
    limpio = re.sub(r'\s+', ' ', (texto or '')).strip()
    if not limpio:
        raise ValueError('Ingresá tu nombre.')
    if len(limpio) > NOMBRE_MAXIMO:
        raise ValueError(f'El nombre admite hasta {NOMBRE_MAXIMO} caracteres.')
    if any(unicodedata.category(c).startswith('C') for c in limpio):
        raise ValueError('El nombre tiene caracteres no permitidos.')
    return limpio


def clave_nombre(nombre):
    """Para comparar nombres: sin mayusculas ni acentos ('Ana' = 'ANA' = 'Aná')."""
    sin_acentos = unicodedata.normalize('NFKD', nombre or '')
    sin_acentos = ''.join(c for c in sin_acentos if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', sin_acentos).strip().casefold()


def estado_inicial_de_comanda(modalidad, ronda_liberada):
    """`retenida` si es una mesa Grupal y la primera ronda todavia no salio; `pendiente` en cualquier otro caso."""
    return RETENIDA if modalidad == GRUPAL and not ronda_liberada else PENDIENTE


def todos_dieron_ok(comensales):
    """`comensales`: lista de (estado, ok). True si hay al menos un comensal activo y todos los activos dieron el OK
    (los retirados no cuentan)."""
    activos = [ok for estado, ok in comensales if estado == ACTIVO]
    return bool(activos) and all(activos)


def faltan_por_ok(comensales):
    """`comensales`: lista de (nombre, estado, ok). Nombres de los activos que todavia no dieron el OK."""
    return [nombre for nombre, estado, ok in comensales if estado == ACTIVO and not ok]


def comandas_a_cancelar(comandas, retirados):
    """`comandas`: lista de (id, id_comensal, estado_en_redis). Devuelve los id de las que se cancelan al retirarse
    `retirados` (conjunto de id de comensal): solo las de esos comensales que no empezaron a prepararse."""
    retirados = set(retirados)
    return [id_comanda for id_comanda, id_comensal, estado in comandas
            if id_comensal in retirados and estado in ESTADOS_CANCELABLES]


def estados_que_bloquean_el_cierre(estados):
    """De los estados en Redis de las comandas aceptadas (None = ya entregada), los que impiden cerrar la mesa."""
    return [estado for estado in estados if estado in ESTADOS_ACTIVOS]


def plan_devolucion(movimientos):
    """Que devolver al stock al cancelar una comanda. `movimientos`: lista de (id_lote, tipo, cantidad) de los movimientos
    de esa comanda ('Consumo' con cantidad negativa y 'Devolucion' con cantidad positiva). Devuelve {id_lote: cantidad a
    devolver} (positiva) solo de lo que todavia no se devolvio, asi cancelar dos veces nunca devuelve de mas."""
    saldo = {}
    for id_lote, tipo, cantidad in movimientos:
        if tipo in ('Consumo', 'Devolucion'):
            saldo[id_lote] = saldo.get(id_lote, Decimal('0')) + Decimal(cantidad)
    return {id_lote: -total for id_lote, total in saldo.items() if total < 0}


def segundos_para_regenerar(ultimo_cambio, ahora, espera=ESPERA_REGENERAR_PIN_SEGUNDOS):
    """Segundos que faltan para poder pedir otro PIN (0 = ya se puede). Fechas como datetime comparables."""
    if ultimo_cambio is None:
        return 0
    faltan = espera - (ahora - ultimo_cambio).total_seconds()
    return max(0, math.ceil(faltan))


def pin_fue_anterior(pin, pins_anteriores):
    """True si el PIN fue el de la mesa antes de un cambio. `pins_anteriores`: texto con los PIN separados por coma."""
    return bool(pin) and pin in [p for p in (pins_anteriores or '').split(',') if p]


def agregar_pin_anterior(pins_anteriores, pin, maximo=8):
    """Suma `pin` al historial de PIN viejos (los mas nuevos al final; guarda hasta `maximo`)."""
    lista = [p for p in (pins_anteriores or '').split(',') if p and p != pin] + [pin]
    return ','.join(lista[-maximo:])


def mensaje_pin_cambiado():
    return 'El PIN de la mesa cambió. Pedile el nuevo al mozo.'


def mensaje_comensal_requerido():
    return 'En una mesa grupal tenés que ingresar tu nombre antes de pedir.'


def mensaje_comensal_retirado():
    return 'Ya no estás en esta mesa. Si volviste, pedile el PIN nuevo al mozo e ingresá otra vez tu nombre.'


def texto_motivo_cancelacion(motivo, items):
    """Para guardar en ComandaRecibida.Motivo: por que se cancelo y que llevaba. `items`: lista de (cantidad, nombre)."""
    detalle = ', '.join(f'{cantidad}x {nombre}' for cantidad, nombre in items)
    texto = f'Cancelada: {motivo}.' + (f' Pedido: {detalle}.' if detalle else '')
    return texto[:500]
