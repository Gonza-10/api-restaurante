"""Calculos de cobros que no usan la base de datos ni internet (se prueban solos con Tests/Scripts/probar_cobros_calculos.py).

Reglas de plata del sistema:
- La cuenta SIEMPRE esta en pesos (ARS). Otras monedas solo existen para cobrar efectivo y para mostrar equivalentes.
- Cotizacion = ARS por 1 unidad de la moneda (tipoCotizacion del BCRA): USD 1450 significa 1 USD = 1450 ARS.
- Redondeo: a centavos, mitad hacia arriba (ROUND_HALF_UP). Se usa Decimal siempre, nunca float.
- Un cobro en efectivo tiene UNA sola moneda (la que entrega el cliente). Si el cliente deja la propina en otra moneda,
  son dos cobros distintos.
- El vuelto SIEMPRE se da en pesos y lo calcula el sistema.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEDA_BASE = 'ARS'
MONEDAS_EXTRANJERAS = ('USD', 'BRL', 'PYG')
MONEDAS = (MONEDA_BASE,) + MONEDAS_EXTRANJERAS

CERO = Decimal('0')
PASO_DINERO = Decimal('0.01')
PASO_COTIZACION = Decimal('0.00000001')  # 8 decimales, como CotizacionMoneda.Valor

DIAS_A_CONSULTAR = 8                 # cuantos dias hacia atras se busca una cotizacion publicada (fines de semana, feriados)
UMBRAL_DESACTUALIZADA_MIN = 120      # sin una consulta exitosa en este tiempo, el estado avisa que esta desactualizada


class RespuestaBcraInvalida(ValueError):
    """La respuesta del BCRA no tiene la forma esperada."""


class CobroInvalido(ValueError):
    """Los montos de un cobro no cierran. El mensaje esta listo para mostrarle al mozo."""


def a_decimal(valor):
    """Convierte a Decimal pasando por texto (un float como 0.1 no se arrastra con su error binario)."""
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f'Numero invalido: {valor!r}')


def redondear_dinero(valor):
    return a_decimal(valor).quantize(PASO_DINERO, rounding=ROUND_HALF_UP)


# ---------- conversiones ----------

def convertir_a_ars(monto, cotizacion):
    """Un monto en otra moneda, en pesos: 100 USD a 1450 -> 145000.00."""
    return redondear_dinero(a_decimal(monto) * a_decimal(cotizacion))


def convertir_desde_ars(monto_ars, cotizacion):
    """Un monto en pesos, en otra moneda: 145000 ARS a 1450 -> 100.00."""
    cot = a_decimal(cotizacion)
    if cot <= 0:
        raise ValueError('La cotizacion debe ser mayor a cero.')
    return redondear_dinero(a_decimal(monto_ars) / cot)


def equivalentes(total_ars, cotizaciones):
    """Cuanto vale un total en pesos en cada moneda extranjera: {'USD': Decimal, 'BRL': Decimal, 'PYG': Decimal}.
    cotizaciones = {moneda: ARS por unidad}. Si falta la cotizacion de una moneda, su equivalente es None."""
    resultado = {}
    for moneda in MONEDAS_EXTRANJERAS:
        cot = cotizaciones.get(moneda)
        resultado[moneda] = convertir_desde_ars(total_ars, cot) if cot is not None and a_decimal(cot) > 0 else None
    return resultado


# ---------- cobro en efectivo ----------

def calcular_cobro_efectivo(recibido_ars, saldo, propina=CERO, monto_cuenta=None):
    """Reparte lo que entrego el cliente (ya convertido a pesos) entre la cuenta, la propina y el vuelto.
    - saldo: lo que todavia se debe de la cuenta.
    - propina: pesos que el cliente deja de propina (0 si no deja).
    - monto_cuenta: cuanto de la cuenta se paga con este cobro. Sin indicar, se paga todo el saldo que alcance.
    Devuelve {'aplicado', 'propina', 'vuelto'} en pesos. Lanza CobroInvalido si los montos no cierran."""
    recibido = redondear_dinero(recibido_ars)
    saldo = redondear_dinero(saldo)
    propina = redondear_dinero(propina)
    if recibido <= 0:
        raise CobroInvalido('El monto recibido debe ser mayor a cero.')
    if propina < 0:
        raise CobroInvalido('La propina no puede ser negativa.')
    if saldo < 0:
        raise CobroInvalido('El saldo de la cuenta no puede ser negativo.')

    if monto_cuenta is None:
        disponible = recibido - propina
        if disponible < 0:
            raise CobroInvalido(f'La propina (${propina}) supera lo recibido (${recibido}).')
        aplicado = min(saldo, disponible)
    else:
        aplicado = redondear_dinero(monto_cuenta)
        if aplicado < 0:
            raise CobroInvalido('El monto de la cuenta no puede ser negativo.')
        if aplicado > saldo:
            raise CobroInvalido(f'El monto (${aplicado}) supera el saldo de la cuenta (${saldo}).')

    if aplicado + propina <= 0:
        raise CobroInvalido('No hay nada para cobrar: ni cuenta ni propina.')

    vuelto = recibido - aplicado - propina
    if vuelto < 0:
        raise CobroInvalido(f'Lo recibido no alcanza: faltan ${-vuelto}.')
    return {'aplicado': aplicado, 'propina': propina, 'vuelto': vuelto}


METODOS_SOLICITABLES = {'efectivo': 'Efectivo', 'mercadopago': 'MercadoPago', 'tarjeta': 'Tarjeta'}


def metodo_pago_solicitado(texto):
    """Medio con el que el cliente dice que quiere pagar, normalizado a 'Efectivo', 'MercadoPago' o 'Tarjeta'. Admite mayusculas,
    espacios, guiones y 'mercado pago'. Cualquier otra cosa (vacio, 'transferencia', 'ninguno'...) devuelve None: es solo un
    aviso para el mozo y no debe hacer fallar la solicitud de la cuenta."""
    if not isinstance(texto, str):
        return None
    clave = ''.join(c for c in texto.lower() if c.isalnum())
    return METODOS_SOLICITABLES.get(clave)


def calcular_propina_tarjeta(propina=None):
    """Propina (en pesos) que el cliente deja al pagar con tarjeta: opcional y nunca negativa. El posnet la cobra junto con la
    cuenta y va solo al mozo de la mesa. Sin dato (None o vacio) es cero. Lanza CobroInvalido si no es un numero o es negativa."""
    if propina is None or (isinstance(propina, str) and not propina.strip()):
        return CERO
    try:
        valor = redondear_dinero(propina)
    except ValueError:
        raise CobroInvalido('La propina no es un numero valido.')
    if not valor.is_finite() or valor < 0:
        raise CobroInvalido('La propina no puede ser negativa.')
    return valor


def calcular_cobro_tarjeta(saldo, monto_cuenta=None):
    """Cuanto de la cuenta cubre un cobro con tarjeta confirmado por el mozo. Sin `monto_cuenta` se cobra todo el saldo.
    No hay vuelto (la propina se valida aparte, con calcular_propina_tarjeta). Lanza CobroInvalido si el saldo es cero o el monto no sirve."""
    saldo = redondear_dinero(saldo)
    if saldo <= 0:
        raise CobroInvalido('La cuenta ya no tiene saldo para cobrar.')
    if monto_cuenta is None:
        return saldo
    monto = redondear_dinero(monto_cuenta)
    if monto <= 0:
        raise CobroInvalido('El monto a cobrar debe ser mayor a cero.')
    if monto > saldo:
        raise CobroInvalido(f'El monto (${monto}) supera el saldo de la cuenta (${saldo}).')
    return monto


# ---------- cotizacion del BCRA ----------

def _valor_positivo(valor):
    """Cotizacion como Decimal con 8 decimales, o None si no sirve (vacia, texto, cero, negativa, infinita)."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = a_decimal(valor)
    except ValueError:
        return None
    if not numero.is_finite():
        return None
    numero = numero.quantize(PASO_COTIZACION, rounding=ROUND_HALF_UP)
    return numero if numero > 0 else None


def _fecha_de(texto):
    try:
        return date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


def parsear_cotizaciones_bcra(datos, monedas=MONEDAS_EXTRANJERAS):
    """Lee la respuesta JSON del BCRA (ya convertida a dict/list de Python).
    Forma esperada (sin verificar contra el BCRA real todavia): {"results": {"fecha": "2026-11-05", "detalle":
    [{"codigoMoneda": "USD", "tipoCotizacion": 1450.5, ...}]}}. Tambien acepta "results" como lista de esos bloques
    (se queda con el de fecha mas reciente que traiga alguna de las monedas pedidas).
    Devuelve (fecha, {moneda: Decimal}); (None, {}) si no trae ninguna. Lanza RespuestaBcraInvalida si no tiene la forma."""
    if not isinstance(datos, dict) or 'results' not in datos:
        raise RespuestaBcraInvalida('La respuesta del BCRA no tiene "results".')
    resultados = datos['results']
    if isinstance(resultados, dict):
        bloques = [resultados]
    elif isinstance(resultados, list):
        bloques = [b for b in resultados if isinstance(b, dict)]
    else:
        raise RespuestaBcraInvalida('"results" del BCRA no es un objeto ni una lista.')

    mejor = (None, {})
    for bloque in bloques:
        detalle = bloque.get('detalle')
        if detalle is None:
            continue
        if not isinstance(detalle, list):
            raise RespuestaBcraInvalida('"detalle" del BCRA no es una lista.')
        valores = {}
        for fila in detalle:
            if not isinstance(fila, dict):
                continue
            codigo = str(fila.get('codigoMoneda') or '').strip().upper()
            if codigo not in monedas:
                continue
            valor = _valor_positivo(fila.get('tipoCotizacion'))
            if valor is not None:
                valores[codigo] = valor
        if not valores:
            continue
        fecha = _fecha_de(bloque.get('fecha'))
        if mejor[1] == {} or (fecha or date.min) > (mejor[0] or date.min):
            mejor = (fecha, valores)
    return mejor


def necesita_guardar(ultimo_valor, nuevo_valor):
    """Se guarda una fila nueva solo si no habia ninguna o si el valor cambio (la cotizacion oficial cambia una vez por dia)."""
    return ultimo_valor is None or a_decimal(ultimo_valor) != a_decimal(nuevo_valor)


def fechas_a_consultar(hoy, dias=DIAS_A_CONSULTAR):
    """Hoy y los dias anteriores, en ese orden: el BCRA no publica los fines de semana ni feriados, asi que se retrocede
    hasta encontrar un dia con cotizacion."""
    return [hoy - timedelta(days=n) for n in range(dias)]


def esta_desactualizada(ultima_consulta, ahora, minutos=UMBRAL_DESACTUALIZADA_MIN):
    """True si nunca se consulto con exito o si la ultima consulta exitosa fue hace mas de `minutos`."""
    if ultima_consulta is None:
        return True
    return (ahora - ultima_consulta) > timedelta(minutes=minutos)
