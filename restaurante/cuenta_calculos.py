"""Calculos de la cuenta que no usan la base de datos (se prueban solos con Tests/Scripts/probar_cuenta_calculos.py).

- Todo en pesos (ARS), Decimal, centavos con redondeo mitad hacia arriba.
- Un plato dividido se reparte en partes iguales entre sus participantes; los centavos que sobran van de a uno a los
  primeros, para que la suma de las partes sea EXACTAMENTE el total (nunca se pierde ni se inventa un centavo).
- El desglose por comensal es informativo: lo que se cobra es el total de la factura.
"""
from decimal import Decimal

from .cobros_calculos import CERO, MONEDA_BASE, PASO_DINERO, a_decimal, convertir_desde_ars, redondear_dinero

SIN_ASIGNAR = 'Sin asignar'

ESTADOS_QUE_RESERVAN_SALDO = ('Aprobado', 'Pendiente')   # un pago pendiente reserva su monto hasta resolverse


def repartir_en_partes(monto, cantidad):
    """Reparte `monto` en `cantidad` partes iguales a centavos. Las primeras partes llevan el centavo que sobra."""
    if cantidad < 1:
        raise ValueError('Tiene que haber al menos una parte.')
    monto = redondear_dinero(monto)
    centavos = int((monto / PASO_DINERO).to_integral_value())
    base, resto = divmod(centavos, cantidad)
    return [(Decimal(base + (1 if i < resto else 0)) * PASO_DINERO).quantize(PASO_DINERO) for i in range(cantidad)]


def desglose_por_comensal(renglones):
    """Cuanto le corresponde a cada comensal. `renglones`: lista de {'sub_total', 'comensal' (o None), 'compartido': [..]}.
    - Con `compartido`: se reparte en partes iguales entre esos participantes.
    - Sin `compartido` y con `comensal`: es de ese comensal.
    - Sin ninguno: queda en 'Sin asignar'.
    Devuelve {nombre: Decimal} en el orden en que aparecen; la suma es el total de los renglones."""
    resultado = {}

    def sumar(nombre, monto):
        resultado[nombre] = resultado.get(nombre, CERO) + monto

    for r in renglones:
        monto = redondear_dinero(r['sub_total'])
        participantes = []
        for nombre in (r.get('compartido') or []):
            nombre = str(nombre).strip()
            if nombre and nombre not in participantes:
                participantes.append(nombre)
        if participantes:
            for nombre, parte in zip(participantes, repartir_en_partes(monto, len(participantes))):
                sumar(nombre, parte)
        else:
            sumar((r.get('comensal') or '').strip() or SIN_ASIGNAR, monto)
    return {nombre: redondear_dinero(total) for nombre, total in resultado.items()}


def saldo_de_la_cuenta(total, pagos):
    """Lo que falta pagar: total - lo ya aprobado - lo pendiente. `pagos`: lista de {'estado', 'monto'} (monto = lo que el
    pago descuenta de la cuenta). Solo cuentan los Aprobados y los Pendientes; los demas estados no reservan nada."""
    reservado = sum((redondear_dinero(p['monto']) for p in pagos if p['estado'] in ESTADOS_QUE_RESERVAN_SALDO), CERO)
    return redondear_dinero(total) - reservado


def total_aprobado(pagos):
    return sum((redondear_dinero(p['monto']) for p in pagos if p['estado'] == 'Aprobado'), CERO)


def partes_de_ingreso(recibido, propina_ars, cotizacion, moneda):
    """Como se anota en la caja lo que entrego el cliente (en su moneda): (venta, propina), con venta + propina = recibido.
    La propina se pasa a la moneda del pago; todo lo demas es venta (incluido lo que se devuelve como vuelto en pesos,
    que sale aparte de la caja como egreso). Si la propina convertida supera lo recibido, se topa en lo recibido."""
    recibido = redondear_dinero(recibido)
    propina_ars = redondear_dinero(propina_ars)
    if propina_ars <= 0:
        return recibido, CERO
    propina = propina_ars if moneda == MONEDA_BASE else convertir_desde_ars(propina_ars, cotizacion)
    propina = min(propina, recibido)
    return recibido - propina, propina


def equivalentes_para_factura(total_ars, cotizaciones):
    """{'USD': .., 'BRL': .., 'PYG': ..} (None si falta la cotizacion), mas las cotizaciones usadas, para guardar la foto."""
    from .cobros_calculos import equivalentes
    return equivalentes(total_ars, cotizaciones)


def descripcion_de_renglon(nombre, quitados, extras=()):
    """'Hamburguesa', 'Hamburguesa (sin cebolla, tomate)' o 'Hamburguesa (sin cebolla; con Cheddar x2)': el texto que
    queda en la factura. `extras`: nombres de los extras que sumo el cliente (cobros, hito 5)."""
    partes = []
    if quitados:
        partes.append(f"sin {', '.join(quitados)}")
    if extras:
        partes.append(f"con {', '.join(extras)}")
    if partes:
        return f"{nombre} ({'; '.join(partes)})"[:150]
    return nombre[:150]
