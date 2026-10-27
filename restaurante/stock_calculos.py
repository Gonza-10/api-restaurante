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


# ==================== RECETAS Y DESCUENTO POR COMANDA (hito 2) ====================
# Una receta dice cuanto gasta UNA unidad vendida: [(id_insumo, cantidad_en_unidad_base), ...].

def porciones_posibles(ingredientes, disponible):
    """Cuantas unidades se pueden preparar con lo que hay. ingredientes: [(id_insumo, cantidad)];
    disponible: {id_insumo: cantidad}. Devuelve (porciones, id_insumo_limitante): el limitante es el insumo que
    primero se acaba (a igual cantidad, el de menor id). Una receta sin ingredientes devuelve (None, None)."""
    mejor = None
    limitante = None
    for id_insumo, cantidad in sorted(ingredientes):
        alcanza = int((a_decimal(disponible.get(id_insumo, CERO)) // a_decimal(cantidad)))
        if mejor is None or alcanza < mejor:
            mejor, limitante = alcanza, id_insumo
    return mejor, limitante


def requerimiento_por_insumo(conteo, recetas):
    """Cuanto de cada insumo necesita un pedido. conteo: {id_producto: cantidad pedida};
    recetas: {id_producto: [(id_insumo, cantidad)]} (los productos sin receta no consumen).
    Devuelve {id_insumo: cantidad_total} con los insumos de todas las recetas sumados."""
    total = {}
    for id_producto, pedido in conteo.items():
        for id_insumo, cantidad in recetas.get(id_producto, ()):
            total[id_insumo] = total.get(id_insumo, CERO) + a_decimal(cantidad) * pedido
    return total


def evaluar_pedido(conteo, recetas, disponible):
    """Decide si alcanza el stock para todo el pedido. Los productos se evaluan en orden de id y cada uno reserva
    lo suyo, asi dos platos que comparten un insumo no cuentan dos veces la misma cantidad.
    Devuelve la lista de faltantes (vacia si alcanza todo):
    [{'id_producto', 'pedido', 'posibles', 'id_insumo_limitante'}], donde `posibles` es cuantas unidades de ese
    producto se pueden preparar (0 si ninguna)."""
    restante = {k: a_decimal(v) for k, v in disponible.items()}
    faltantes = []
    for id_producto in sorted(conteo):
        ingredientes = recetas.get(id_producto)
        if not ingredientes:
            continue
        pedido = conteo[id_producto]
        posibles, limitante = porciones_posibles(ingredientes, restante)
        if posibles is None:
            continue
        reservar = min(posibles, pedido)
        for id_insumo, cantidad in ingredientes:
            restante[id_insumo] = restante.get(id_insumo, CERO) - a_decimal(cantidad) * reservar
        if posibles < pedido:
            faltantes.append({
                'id_producto': id_producto, 'pedido': pedido, 'posibles': posibles, 'id_insumo_limitante': limitante,
            })
    return faltantes


def mensaje_cliente_faltantes(faltantes, nombres_producto):
    """Mensaje generico para el cliente: nunca dice que insumo falta, solo cuanto se puede preparar de cada plato."""
    partes = []
    for f in faltantes:
        nombre = nombres_producto.get(f['id_producto'], 'el plato')
        if f['posibles'] > 0:
            partes.append(f"Podemos preparar solamente {f['posibles']} de {f['pedido']} {nombre}")
        else:
            partes.append(f'Por ahora no podemos preparar {nombre}')
    return 'Insumos insuficientes. ' + '. '.join(partes) + '. Disculpe las molestias.'


def motivo_interno_faltantes(faltantes, nombres_producto, nombres_insumo):
    """Detalle para el personal: que plato, cuantos alcanzan y que insumo limita."""
    partes = []
    for f in faltantes:
        partes.append(
            f"{nombres_producto.get(f['id_producto'], f['id_producto'])}: pedidos {f['pedido']}, "
            f"alcanzan {f['posibles']}; limita {nombres_insumo.get(f['id_insumo_limitante'], f['id_insumo_limitante'])}"
        )
    return '; '.join(partes)


def costo_de_receta(lineas):
    """Costo de una unidad de la receta. lineas: [(cantidad, costo_unitario)] con el costo de reposicion por unidad
    base. Devuelve (total, completo): completo es False si algun insumo no tiene costo (nunca se compro)."""
    total = CERO
    completo = True
    for cantidad, costo in lineas:
        if costo is None or a_decimal(costo) <= 0:
            completo = False
            continue
        total += a_decimal(cantidad) * a_decimal(costo)
    return redondear_dinero(total), completo


# ==================== DISPONIBILIDAD Y NOTIFICACIONES (hito 3) ====================

def insumos_faltantes(ingredientes, disponible):
    """Ids de los insumos de la receta que no alcanzan para UNA unidad completa (de menor a mayor id)."""
    return sorted(
        id_insumo for id_insumo, cantidad in ingredientes
        if a_decimal(disponible.get(id_insumo, CERO)) < a_decimal(cantidad)
    )


def hay_para_una(ingredientes, disponible):
    """Un plato se ofrece mientras haya stock para UNA unidad completa de su receta (nunca una fraccion).
    Sin ingredientes (sin receta) no hay control de stock: siempre se ofrece."""
    return not ingredientes or not insumos_faltantes(ingredientes, disponible)


# De lo mas urgente a lo menos urgente; dentro de cada severidad, por tipo y despues por nombre.
SEVERIDADES = ('urgente', 'aviso', 'info')
TIPOS_NOTIFICACION = ('plato_sin_insumos', 'insumo_critico', 'se_puede_reactivar')


def clave_notificacion(notificacion):
    """Clave para ordenar las notificaciones del panel de Cocina."""
    return (
        SEVERIDADES.index(notificacion['severidad']),
        TIPOS_NOTIFICACION.index(notificacion['tipo']),
        notificacion['mensaje'].lower(),
    )


def resumen_notificaciones(notificaciones):
    """Cantidades para el numerito de la pestana de notificaciones."""
    por_tipo = {tipo: 0 for tipo in TIPOS_NOTIFICACION}
    por_severidad = {severidad: 0 for severidad in SEVERIDADES}
    for n in notificaciones:
        por_tipo[n['tipo']] += 1
        por_severidad[n['severidad']] += 1
    return {'total': len(notificaciones), 'por_tipo': por_tipo, 'por_severidad': por_severidad}
