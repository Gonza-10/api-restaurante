"""Calculos de caja que no usan la base de datos (se prueban solos con Tests/Scripts/probar_caja_calculos.py).

- El arqueo tiene dos medios: EFECTIVO (el cajon, por moneda: ARS, USD, BRL y PYG) y MERCADOPAGO (dinero digital en la
  cuenta del restaurante; siempre en pesos).
- Esperado de efectivo = apertura + ingresos - egresos (de esa moneda). Esperado de Mercado Pago = ingresos - egresos
  del periodo de la caja (cobros aprobados): no hay apertura porque la cuenta digital no se vacia al cerrar.
- Diferencia = declarado - esperado: negativo es faltante y positivo es sobrante.
- Dinero siempre en Decimal, con centavos (redondeo mitad hacia arriba).
"""
from decimal import Decimal

from .cobros_calculos import CERO, MONEDA_BASE, MONEDAS, a_decimal, convertir_a_ars, redondear_dinero

MONTO_MAXIMO = Decimal('99999999999.99')   # tope por monto: la base guarda DECIMAL(14,2)

MEDIO_EFECTIVO = 'Efectivo'
MEDIO_MERCADO_PAGO = 'MercadoPago'
MEDIOS = (MEDIO_EFECTIVO, MEDIO_MERCADO_PAGO)

TIPOS_MOVIMIENTO = ('Ingreso', 'Egreso')
CONCEPTOS = ('Manual', 'Venta', 'Propina', 'Vuelto', 'Anulacion')


class CajaInvalida(ValueError):
    """Datos de caja que no se pueden aceptar. El mensaje esta listo para mostrar."""


def validar_monto(valor, nombre='monto', positivo=False):
    """Un monto de dinero: numero (o texto numerico), no negativo, con a lo sumo 2 decimales y por debajo del tope.
    `positivo=True` exige mayor que cero (los movimientos). Devuelve Decimal."""
    if valor is None or isinstance(valor, bool) or (isinstance(valor, str) and not valor.strip()):
        raise CajaInvalida(f'Falta {nombre}.')
    try:
        monto = a_decimal(valor)
    except ValueError:
        raise CajaInvalida(f'{nombre}: no es un numero valido.')
    if not monto.is_finite():
        raise CajaInvalida(f'{nombre}: no es un numero valido.')
    if monto < 0:
        raise CajaInvalida(f'{nombre}: no puede ser negativo.')
    if positivo and monto == 0:
        raise CajaInvalida(f'{nombre}: debe ser mayor a cero.')
    if monto > MONTO_MAXIMO:
        raise CajaInvalida(f'{nombre}: es demasiado grande.')
    if monto != redondear_dinero(monto):
        raise CajaInvalida(f'{nombre}: admite como maximo 2 decimales.')
    return redondear_dinero(monto)


def validar_moneda(valor):
    moneda = str(valor or '').strip().upper()
    if moneda not in MONEDAS:
        raise CajaInvalida(f"Moneda invalida. Valores validos: {', '.join(MONEDAS)}.")
    return moneda


def validar_montos_por_moneda(datos, obligatorias=False):
    """Un diccionario {moneda: monto} (apertura o recuento de cierre). Devuelve {moneda: Decimal} con las cuatro monedas.
    `obligatorias=True` exige las cuatro (el cierre: contar 0 tambien es contar). Si no, las que faltan quedan en 0."""
    if datos is None:
        datos = {}
    if not isinstance(datos, dict):
        raise CajaInvalida('Los montos deben enviarse como un objeto: {"ARS": 10000, "USD": 0, "BRL": 0, "PYG": 0}.')
    desconocidas = [k for k in datos if str(k).strip().upper() not in MONEDAS]
    if desconocidas:
        raise CajaInvalida(f"Moneda desconocida: {', '.join(map(str, desconocidas))}. Valores validos: {', '.join(MONEDAS)}.")
    normalizado = {}
    for clave, valor in datos.items():
        moneda = str(clave).strip().upper()
        if moneda in normalizado:
            raise CajaInvalida(f'La moneda {moneda} esta repetida.')
        normalizado[moneda] = valor
    faltan = [m for m in MONEDAS if m not in normalizado]
    if obligatorias and faltan:
        raise CajaInvalida(f"Falta contar: {', '.join(faltan)}. Informar las cuatro monedas (0 si no hay).")
    return {m: validar_monto(normalizado[m], f'Monto en {m}') if m in normalizado else CERO for m in MONEDAS}


def esperado(apertura, ingresos, egresos):
    """Lo que tiene que haber en el cajon de una moneda."""
    return redondear_dinero(a_decimal(apertura) + a_decimal(ingresos) - a_decimal(egresos))


def diferencia(declarado, esperado_):
    """Declarado menos esperado: negativo = faltante, positivo = sobrante."""
    return redondear_dinero(a_decimal(declarado) - a_decimal(esperado_))


def arqueo(apertura, ingresos, egresos, declarado=None):
    """Arqueo de una caja. Los parametros son diccionarios {moneda: monto}; los que falten valen 0.
    Devuelve {moneda: {'apertura', 'ingresos', 'egresos', 'esperado', 'declarado', 'diferencia'}}.
    Sin `declarado` (caja abierta) solo hay esperado."""
    resultado = {}
    for moneda in MONEDAS:
        ap = a_decimal((apertura or {}).get(moneda, CERO))
        ing = a_decimal((ingresos or {}).get(moneda, CERO))
        egr = a_decimal((egresos or {}).get(moneda, CERO))
        esp = esperado(ap, ing, egr)
        decl = None if declarado is None else a_decimal(declarado.get(moneda, CERO))
        resultado[moneda] = {
            'apertura': redondear_dinero(ap),
            'ingresos': redondear_dinero(ing),
            'egresos': redondear_dinero(egr),
            'esperado': esp,
            'declarado': None if decl is None else redondear_dinero(decl),
            'diferencia': None if decl is None else diferencia(decl, esp),
        }
    return resultado


def hay_diferencias(resultado_arqueo):
    return any(f['diferencia'] not in (None, CERO) for f in resultado_arqueo.values())


def egreso_posible(esperado_actual, monto):
    """Un egreso no puede dejar el cajon en negativo: no se puede sacar mas plata de la que hay en esa moneda."""
    return a_decimal(monto) <= a_decimal(esperado_actual)


# ---------- Mercado Pago (dinero digital) ----------

def arqueo_digital(ingresos, egresos, declarado=None):
    """Arqueo de Mercado Pago: lo que el sistema registro como cobrado (pagos aprobados) contra lo que figura acreditado
    en la cuenta. Siempre en pesos. Sin `declarado` (caja abierta) solo hay esperado."""
    ing = redondear_dinero(a_decimal(ingresos or CERO))
    egr = redondear_dinero(a_decimal(egresos or CERO))
    esp = redondear_dinero(ing - egr)
    decl = None if declarado is None else redondear_dinero(a_decimal(declarado))
    return {
        'moneda': MONEDA_BASE,
        'ingresos': ing,
        'egresos': egr,
        'esperado': esp,
        'declarado': decl,
        'diferencia': None if decl is None else diferencia(decl, esp),
    }


def total_en_pesos(montos_por_moneda, cotizaciones, mercado_pago=CERO):
    """Efectivo de todas las monedas pasado a pesos con las cotizaciones dadas ({moneda: ARS por unidad}) mas el dinero
    digital. Devuelve {'efectivo', 'mercado_pago', 'total'} (todo en pesos) o None si hay una moneda con plata y sin
    cotizacion (no se inventa un valor)."""
    efectivo = CERO
    for moneda in MONEDAS:
        monto = a_decimal((montos_por_moneda or {}).get(moneda, CERO))
        if monto == 0:
            continue
        if moneda == MONEDA_BASE:
            efectivo += monto
        elif moneda in cotizaciones:
            efectivo += convertir_a_ars(monto, cotizaciones[moneda])
        else:
            return None
    efectivo = redondear_dinero(efectivo)
    digital = redondear_dinero(a_decimal(mercado_pago or CERO))
    return {'efectivo': efectivo, 'mercado_pago': digital, 'total': redondear_dinero(efectivo + digital)}


def validar_mercado_pago(valor, esperado_mp):
    """Lo acreditado en Mercado Pago que se declara al cerrar. Si no se informa y el sistema registro cobros, es un error
    (hay que mirar la cuenta); si no hubo cobros, se toma 0."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if a_decimal(esperado_mp) != 0:
            raise CajaInvalida(
                f'Falta informar lo acreditado en Mercado Pago (el sistema registro {redondear_dinero(esperado_mp)}). '
                'Mirarlo en la cuenta de Mercado Pago; si no se acredito nada, informar 0.')
        return CERO
    return validar_monto(valor, 'Monto acreditado en Mercado Pago')


def hay_diferencias_caja(resumen):
    """True si algun medio (efectivo en alguna moneda, o Mercado Pago) cerro con diferencia. `resumen` es el arqueo
    completo: {'efectivo': {...}, 'mercado_pago': {...}}."""
    return hay_diferencias(resumen['efectivo']) or resumen['mercado_pago']['diferencia'] not in (None, CERO)


def advertencias_de_diferencias(resumen):
    """Un aviso (texto) por cada medio/moneda con faltante o sobrante."""
    avisos = []
    filas = [(f'{moneda} en efectivo', fila) for moneda, fila in resumen['efectivo'].items()]
    filas.append(('ARS en Mercado Pago', resumen['mercado_pago']))
    for nombre, fila in filas:
        dif = fila['diferencia']
        if dif is None or dif == 0:
            continue
        tipo = 'faltante' if dif < 0 else 'sobrante'
        avisos.append(f"Hay un {tipo} de {abs(dif)} {nombre} (esperado {fila['esperado']}, informado {fila['declarado']}).")
    return avisos
