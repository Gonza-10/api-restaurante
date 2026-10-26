"""Calculos del stock que no tocan la base de datos (por eso se pueden probar solos).

Todas las cantidades viven en UNIDAD BASE: gramos (Masa), mililitros (Volumen) o unidades (Unidad).
Kilos y litros son solo una forma de mostrarlas.
"""
from decimal import Decimal, ROUND_HALF_UP

CERO = Decimal('0')
PASO_CANTIDAD = Decimal('0.001')    # DECIMAL(12,3)
PASO_COSTO = Decimal('0.000001')    # DECIMAL(14,6): costo por unidad base
PASO_DINERO = Decimal('0.01')

TIPOS_MEDIDA = ('Masa', 'Volumen', 'Unidad')
UNIDAD_BASE = {'Masa': 'g', 'Volumen': 'ml', 'Unidad': 'u'}

# Orden de gravedad: lo que hay que mirar primero va arriba. Un promedio general esconderia un insumo
# esencial en rojo detras de varios en verde, por eso el stock se muestra insumo por insumo.
ESTADOS_STOCK = ('Agotado', 'Critico', 'Bajo', 'SinObjetivo', 'Ok')
SEMAFORO = {'Agotado': 'rojo', 'Critico': 'rojo', 'Bajo': 'amarillo', 'SinObjetivo': 'gris', 'Ok': 'verde'}
REQUIEREN_ATENCION = ('Agotado', 'Critico', 'Bajo')


def a_decimal(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def cuantizar_cantidad(valor):
    return a_decimal(valor).quantize(PASO_CANTIDAD, rounding=ROUND_HALF_UP)


def costo_unitario(costo_total, cantidad):
    """Costo por unidad base de un lote: lo que se pago dividido lo que entro."""
    cantidad = a_decimal(cantidad)
    if cantidad <= 0:
        raise ValueError('La cantidad debe ser mayor que cero.')
    return (a_decimal(costo_total) / cantidad).quantize(PASO_COSTO, rounding=ROUND_HALF_UP)


def costo_total_lote(cantidad_inicial, costo_unit):
    return (a_decimal(cantidad_inicial) * a_decimal(costo_unit)).quantize(PASO_DINERO, rounding=ROUND_HALF_UP)


def redondear_dinero(valor):
    return a_decimal(valor).quantize(PASO_DINERO, rounding=ROUND_HALF_UP)


def repartir_fefo(disponibles, cantidad):
    """Reparte una cantidad entre lotes ya ordenados (el que vence antes primero).
    disponibles: [(id_lote, cantidad_disponible), ...]. Devuelve (tomas, faltante):
    tomas = [(id_lote, cantidad_a_tomar), ...] y faltante = lo que no alcanzo a cubrirse (0 si alcanzo)."""
    restante = a_decimal(cantidad)
    tomas = []
    for id_lote, disponible in disponibles:
        if restante <= 0:
            break
        tomar = min(a_decimal(disponible), restante)
        if tomar > 0:
            tomas.append((id_lote, tomar))
            restante -= tomar
    return tomas, restante


def es_entera(valor):
    return a_decimal(valor) == a_decimal(valor).to_integral_value()


def texto_cantidad(valor, tipo_medida):
    """'150 kg', '2,5 l', '12 u': solo para mostrar. Masa y Volumen pasan a kg / l desde 1000."""
    valor = a_decimal(valor)
    unidad = UNIDAD_BASE[tipo_medida]
    if tipo_medida in ('Masa', 'Volumen') and abs(valor) >= 1000:
        valor = valor / 1000
        unidad = 'kg' if tipo_medida == 'Masa' else 'l'
    redondeado = valor.quantize(PASO_DINERO, rounding=ROUND_HALF_UP) if unidad != 'u' else valor.quantize(PASO_CANTIDAD)
    texto = format(redondeado.normalize(), 'f')
    return f'{texto} {unidad}'


def clave_gravedad(estado, porcentaje, nombre):
    """Clave para ordenar: primero lo mas grave; a igual estado, el de menor porcentaje; despues por nombre."""
    return (ESTADOS_STOCK.index(estado), a_decimal(porcentaje) if porcentaje is not None else Decimal('1000'), nombre.lower())


def resumen_estados(estados):
    """Cuenta insumos por estado. Nunca promedia: lo que importa es cuantos estan mal, no el promedio."""
    cuentas = {estado: 0 for estado in ESTADOS_STOCK}
    for estado in estados:
        cuentas[estado] += 1
    peor = next((e for e in ESTADOS_STOCK if cuentas[e] and e != 'SinObjetivo'), None)
    if peor is None:
        peor = 'SinObjetivo' if cuentas['SinObjetivo'] else None
    return {
        'total': sum(cuentas.values()),
        'por_estado': cuentas,
        'requieren_atencion': sum(cuentas[e] for e in REQUIEREN_ATENCION),
        'peor_estado': peor,
        'semaforo_general': SEMAFORO[peor] if peor else None,
    }
