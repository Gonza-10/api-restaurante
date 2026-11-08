"""Calculos del stock que no tocan la base de datos (por eso se pueden probar solos).

Todas las cantidades viven en UNIDAD BASE: gramos (Masa), mililitros (Volumen) o unidades (Unidad).
Kilos y litros son solo una forma de mostrarlas.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

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


# Una LINEA de pedido es un producto con sus modificadores: (id_producto, (ids de insumos quitados), (extras)), donde cada
# extra es (id_extra, unidades por unidad de plato) (cobros, hito 5). Dos unidades del mismo plato son la misma linea solo
# si piden lo mismo. Sin extras la clave es (id_producto, quitados), como antes. Por compatibilidad, un entero (solo el id
# del producto) es una linea sin modificadores.

def clave_de_linea(id_producto, sin=(), extras=()):
    """La clave de una linea: (id_producto, ids de los insumos quitados ordenados y sin repetir[, extras ordenados])."""
    quitados = tuple(sorted(set(sin or ())))
    agregados = tuple(sorted((int(i), int(n)) for i, n in (extras or ())))
    return (id_producto, quitados, agregados) if agregados else (id_producto, quitados)


def id_de_linea(clave):
    return clave[0] if isinstance(clave, tuple) else clave


def sin_de_linea(clave):
    return tuple(clave[1]) if isinstance(clave, tuple) else ()


def extras_de_linea(clave):
    """[(id_extra, unidades por unidad de plato)] de una linea (vacio si no pidio extras)."""
    return tuple(clave[2]) if isinstance(clave, tuple) and len(clave) > 2 else ()


def receta_efectiva(ingredientes, sin):
    """La receta de una unidad SIN los ingredientes quitados: [(id_insumo, cantidad)] sin esos insumos."""
    quitados = set(sin or ())
    return [(id_insumo, cantidad) for id_insumo, cantidad in ingredientes if id_insumo not in quitados]


def receta_con_extras(ingredientes, agregados):
    """La receta de una unidad CON sus extras: suma al gasto de cada insumo lo que gastan los extras (si el extra es de un
    insumo que la receta ya usa -mas cheddar- se suma a esa linea; si no, se agrega). ingredientes: [(id_insumo, cantidad)];
    agregados: [(id_insumo, cantidad total del extra por unidad de plato)]."""
    total = {}
    for id_insumo, cantidad in list(ingredientes) + list(agregados):
        total[id_insumo] = total.get(id_insumo, CERO) + a_decimal(cantidad)
    return list(total.items())


def precio_de_renglon(precio_plato, extras):
    """Precio de UNA unidad del renglon: el plato mas los recargos. extras: [(precio por unidad de extra, unidades)]."""
    return a_decimal(precio_plato) + sum((a_decimal(precio) * n for precio, n in extras), CERO)


def requerimiento_por_insumo(conteo, recetas):
    """Cuanto de cada insumo necesita un pedido. conteo: {linea: cantidad pedida} (la linea es un id de producto o
    (id_producto, quitados)); recetas: {linea: [(id_insumo, cantidad)]} ya con lo quitado descontado (los productos
    sin receta no consumen). Devuelve {id_insumo: cantidad_total} con los insumos de todas las recetas sumados."""
    total = {}
    for linea, pedido in conteo.items():
        for id_insumo, cantidad in recetas.get(linea, ()):
            total[id_insumo] = total.get(id_insumo, CERO) + a_decimal(cantidad) * pedido
    return total


def evaluar_pedido(conteo, recetas, disponible):
    """Decide si alcanza el stock para todo el pedido. Las lineas se evaluan en orden y cada una reserva lo suyo, asi
    dos platos que comparten un insumo no cuentan dos veces la misma cantidad.
    conteo: {linea: cantidad pedida}; recetas: {linea: [(id_insumo, cantidad)]} (la receta efectiva de esa linea).
    Devuelve la lista de faltantes (vacia si alcanza todo), UNO POR PRODUCTO aunque lo pidan con distintos
    modificadores: [{'id_producto', 'pedido', 'posibles', 'id_insumo_limitante'}], donde `pedido` y `posibles`
    suman todas las lineas de ese producto (posibles = cuantas unidades se pueden preparar, 0 si ninguna)."""
    restante = {k: a_decimal(v) for k, v in disponible.items()}
    por_producto = {}
    for linea in sorted(conteo):
        ingredientes = recetas.get(linea)
        if not ingredientes:
            continue
        pedido = conteo[linea]
        posibles, limitante = porciones_posibles(ingredientes, restante)
        if posibles is None:
            continue
        reservar = min(posibles, pedido)
        for id_insumo, cantidad in ingredientes:
            restante[id_insumo] = restante.get(id_insumo, CERO) - a_decimal(cantidad) * reservar
        id_producto = id_de_linea(linea)
        acumulado = por_producto.setdefault(
            id_producto, {'id_producto': id_producto, 'pedido': 0, 'posibles': 0, 'id_insumo_limitante': None}
        )
        acumulado['pedido'] += pedido
        acumulado['posibles'] += reservar
        if posibles < pedido and acumulado['id_insumo_limitante'] is None:
            acumulado['id_insumo_limitante'] = limitante
    return [a for a in por_producto.values() if a['posibles'] < a['pedido']]


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
TIPOS_NOTIFICACION = (
    'lote_vencido', 'plato_sin_insumos', 'insumo_critico', 'lote_por_vencer', 'elaboracion_a_producir', 'se_puede_reactivar',
)


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


# ==================== PERDIDAS (hito 4) ====================

# Lista CERRADA de motivos (codigo, etiqueta que se muestra). Cerrada a proposito: con texto libre despues no se
# podria agrupar para saber donde y por que se pierde mas. Si hace falta un motivo nuevo se agrega aca y en el
# CHECK de la tabla Perdida (script 13). 'otro' obliga a escribir una nota.
MOTIVOS_PERDIDA = (
    ('vencimiento', 'Vencimiento'),
    ('rotura_derrame', 'Rotura o derrame'),
    ('error_cocina', 'Error de cocina'),
    ('devolucion_cliente', 'Devolución de cliente'),
    ('consumo_personal', 'Consumo del personal'),
    ('otro', 'Otro'),
)
CODIGOS_MOTIVO = tuple(codigo for codigo, _ in MOTIVOS_PERDIDA)
ETIQUETA_MOTIVO = dict(MOTIVOS_PERDIDA)
MOTIVO_OTRO = 'otro'
MOTIVO_VENCIMIENTO = 'vencimiento'


def valorizar_tomas(tomas):
    """Valor de lo perdido a COSTO REAL de los lotes de donde salio (nunca un promedio).
    tomas: [(cantidad, costo_unitario_del_lote)]; la cantidad puede venir con signo (del libro sale negativa).
    Devuelve (valor, completo): completo es False si algun lote tiene costo cero (insumo que nunca se compro), porque
    entonces el valor queda por debajo del real."""
    total = CERO
    completo = True
    for cantidad, costo in tomas:
        costo = a_decimal(costo) if costo is not None else CERO
        if costo <= 0:
            completo = False
        total += abs(a_decimal(cantidad)) * costo
    return redondear_dinero(total), completo


def resumen_perdidas(filas, limite_items=10):
    """Resumen para Admin y Gerente. filas: [{'tipo': 'insumo'|'plato', 'id': int, 'nombre': str, 'motivo': codigo,
    'valor': Decimal, 'completo': bool}], una por perdida registrada.
    Devuelve el total, el reparto por motivo (con el porcentaje del VALOR perdido que explica cada uno), el reparto
    insumo/plato y los items que mas pierden. Ordenado de mayor a menor valor, y a igual valor por nombre."""
    valor_total = CERO
    por_motivo = {}
    por_tipo = {'insumo': [0, CERO], 'plato': [0, CERO]}
    por_item = {}
    completo = True
    for fila in filas:
        valor = a_decimal(fila['valor'])
        valor_total += valor
        completo = completo and bool(fila.get('completo', True))
        acumulado = por_motivo.setdefault(fila['motivo'], [0, CERO])
        acumulado[0] += 1
        acumulado[1] += valor
        por_tipo[fila['tipo']][0] += 1
        por_tipo[fila['tipo']][1] += valor
        item = por_item.setdefault((fila['tipo'], fila['id']), [fila['nombre'], 0, CERO])
        item[1] += 1
        item[2] += valor

    motivos = []
    for codigo, (registros, valor) in por_motivo.items():
        motivos.append({
            'motivo': codigo,
            'etiqueta': ETIQUETA_MOTIVO.get(codigo, codigo),
            'registros': registros,
            'valor': redondear_dinero(valor),
            'porcentaje': float((valor * 100 / valor_total).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
            if valor_total > 0 else None,
        })
    motivos.sort(key=lambda m: (-m['valor'], m['etiqueta'].lower()))

    items = [
        {'tipo': clave[0], 'id': clave[1], 'nombre': datos[0], 'registros': datos[1], 'valor': redondear_dinero(datos[2])}
        for clave, datos in por_item.items()
    ]
    items.sort(key=lambda i: (-i['valor'], i['nombre'].lower()))

    return {
        'registros': len(filas),
        'valor_total': redondear_dinero(valor_total),
        'valor_completo': completo,
        'por_motivo': motivos,
        'por_tipo': {
            tipo: {'registros': datos[0], 'valor': redondear_dinero(datos[1])} for tipo, datos in por_tipo.items()
        },
        'items_que_mas_pierden': items[:limite_items],
    }


# ==================== ELABORACIONES, VENCIMIENTOS Y REPOSICION (hito 6) ====================

def hay_ciclo(dependencias, producido, ingredientes):
    """True si hacer que `producido` se elabore con `ingredientes` crearia un ciclo (una elaboracion que, directa o
    indirectamente, necesita de si misma). dependencias: {id_insumo_producido: [ids de sus ingredientes]} de las
    elaboraciones que YA existen (sin la que se esta guardando)."""
    pendientes = list(ingredientes)
    vistos = set()
    while pendientes:
        actual = pendientes.pop()
        if actual == producido:
            return True
        if actual in vistos:
            continue
        vistos.add(actual)
        pendientes.extend(dependencias.get(actual, ()))
    return False


def calcular_produccion(ingredientes, rinde, tandas, tipo_producido):
    """Que se necesita para elaborar `tandas` tandas. ingredientes: [(id_insumo, cantidad_por_tanda, tipo_medida,
    nombre)]; rinde: cuanto sale de UNA tanda. Devuelve {'cantidad': lo que sale, 'necesario': [(id_insumo, cantidad)]
    ordenado por id, 'errores': [{'campo', 'mensaje'}]}. Las unidades no se parten: si algo que se cuenta en unidades
    (un huevo, o el propio producto) diera una fraccion, es un error y hay que elegir otra cantidad de tandas."""
    tandas = a_decimal(tandas)
    errores = []
    cantidad_cruda = a_decimal(rinde) * tandas
    if tipo_producido == 'Unidad' and not es_entera(cantidad_cruda):
        errores.append({'campo': 'tandas', 'mensaje': (
            f'Con {format(tandas.normalize(), "f")} tandas saldrian {format(cantidad_cruda.normalize(), "f")} unidades: '
            'tiene que dar una cantidad entera.'
        )})
    necesario = []
    for id_insumo, cantidad, tipo_medida, nombre in sorted(ingredientes, key=lambda x: x[0]):
        cruda = a_decimal(cantidad) * tandas
        if tipo_medida == 'Unidad' and not es_entera(cruda):
            errores.append({'campo': 'tandas', 'mensaje': (
                f'Con {format(tandas.normalize(), "f")} tandas se necesitarian {format(cruda.normalize(), "f")} unidades '
                f'de {nombre}: tiene que dar una cantidad entera.'
            )})
        necesario.append((id_insumo, cuantizar_cantidad(cruda)))
    return {'cantidad': cuantizar_cantidad(cantidad_cruda), 'necesario': necesario, 'errores': errores}


def costo_unitario_producido(tomas, cantidad_producida):
    """Costo real por unidad base de lo elaborado: lo que costaron los lotes que se consumieron (a su costo, nunca un
    promedio) dividido lo que salio. tomas: [(cantidad, costo_unitario_del_lote)]. Devuelve (costo_unitario, completo);
    completo es False si algun lote consumido no tenia costo, y entonces el costo queda por debajo del real."""
    valor, completo = valorizar_tomas(tomas)
    if valor <= 0:
        return CERO, completo
    return costo_unitario(valor, cantidad_producida), completo


MIN_DIAS_AVISO = 0
MAX_DIAS_AVISO = 365
DIAS_AVISO_POR_DEFECTO = 5


def dias_restantes(fecha_vencimiento, hoy):
    """Dias que faltan para que venza (0 = vence hoy, negativo = ya vencio). Un lote se puede usar hasta el dia de
    su vencimiento inclusive."""
    return (fecha_vencimiento - hoy).days


def estado_vencimiento(dias, dias_aviso):
    """'vencido' (ya paso la fecha), 'por_vencer' (faltan `dias_aviso` dias o menos) o None (todavia falta)."""
    if dias < 0:
        return 'vencido'
    if dias <= dias_aviso:
        return 'por_vencer'
    return None


def texto_dias_vencimiento(dias):
    if dias < 0:
        atras = -dias
        return 'vencio ayer' if atras == 1 else f'vencio hace {atras} dias'
    if dias == 0:
        return 'vence hoy'
    if dias == 1:
        return 'vence manana'
    return f'vence en {dias} dias'


def clave_vencimiento(fila):
    """Orden de los lotes en los avisos: el que vence antes primero, y a igual fecha por nombre."""
    return (fila['dias_restantes'], fila['insumo_nombre'].lower(), fila['lote'])


def faltante_a_objetivo(stock, objetivo):
    """Cuanto falta para llegar al stock objetivo (0 si ya se llego o lo supero)."""
    return max(CERO, a_decimal(objetivo) - a_decimal(stock))


def tandas_para(faltante, rinde):
    """Tandas enteras necesarias para cubrir `faltante` con una elaboracion que rinde `rinde` por tanda."""
    return int((a_decimal(faltante) / a_decimal(rinde)).to_integral_value(rounding=ROUND_CEILING))


def entra_en_reposicion(estado, stock, objetivo, todos=False):
    """Un insumo entra en la lista de reposicion si tiene objetivo y esta mal (agotado, critico o bajo). Con
    todos=True entra cualquiera que este por debajo de su objetivo."""
    if a_decimal(objetivo) <= 0:
        return False
    if todos:
        return a_decimal(stock) < a_decimal(objetivo)
    return estado in REQUIEREN_ATENCION


# ---------- Aviso de vencimiento por insumo y reposicion con stock util (hito 6.1) ----------

def ventana_aviso(propio, general):
    """Dias de anticipacion con que se avisa un vencimiento de un insumo: los suyos si los tiene (0 vale: avisa recien
    el dia que vence) y, si no, los generales de la configuracion."""
    return general if propio is None else propio


def estado_de_stock(stock, objetivo, umbral_bajo, umbral_critico):
    """Estado y porcentaje de un stock respecto de su objetivo, con la MISMA regla que la vista vw_StockInsumo.
    Devuelve (estado, porcentaje); el porcentaje es None si el insumo no tiene objetivo."""
    stock = a_decimal(stock)
    objetivo = a_decimal(objetivo)
    porcentaje = (stock * 100 / objetivo).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP) if objetivo > 0 else None
    if stock <= 0:
        return 'Agotado', porcentaje
    if porcentaje is None:
        return 'SinObjetivo', None
    if porcentaje <= umbral_critico:
        return 'Critico', porcentaje
    if porcentaje <= umbral_bajo:
        return 'Bajo', porcentaje
    return 'Ok', porcentaje


def orden_elaboraciones(recetas):
    """Ids de las elaboraciones en orden de arriba hacia abajo: primero las que usan a otras elaboraciones, y despues
    las que ellas usan (la salsa picante antes que la salsa base). recetas: {id_producido: {'ingredientes': [(id, cant)]}}.
    Las elaboraciones no tienen ciclos (la aplicacion los impide); aun asi nunca se visita dos veces la misma."""
    visitadas = set()
    posorden = []

    def visitar(id_producido):
        if id_producido in visitadas:
            return
        visitadas.add(id_producido)
        for id_ingrediente, _ in recetas[id_producido]['ingredientes']:
            if id_ingrediente in recetas:
                visitar(id_ingrediente)
        posorden.append(id_producido)

    for id_producido in sorted(recetas):
        visitar(id_producido)
    return list(reversed(posorden))


def profundidad_elaboracion(id_producido, recetas, memo=None):
    """0 si la elaboracion solo usa insumos comprados; 1 mas que la mas profunda de las elaboraciones que usa. Sirve
    para ordenar la cocina: primero lo que otras elaboraciones necesitan."""
    memo = {} if memo is None else memo
    if id_producido in memo:
        return memo[id_producido]
    memo[id_producido] = 0  # corta cualquier ciclo imposible
    hijos = [i for i, _ in recetas[id_producido]['ingredientes'] if i in recetas]
    memo[id_producido] = 1 + max(profundidad_elaboracion(h, recetas, memo) for h in hijos) if hijos else 0
    return memo[id_producido]


def plan_reposicion(filas, recetas=None, todos=False, costo_de=None):
    """Lista de reposicion. Dos ideas que la hacen confiable:

    1) STOCK UTIL: lo que va a vencer dentro de su ventana de aviso (o ya vencio) no se cuenta como stock, porque no se
       va a poder usar. El estado y lo que falta para el objetivo se calculan con el stock util.
    2) ELABORAR NECESITA INGREDIENTES: cada elaboracion que hay que producir (por estar baja, o porque otra elaboracion
       la necesita) pide sus ingredientes. Lo que no alcance con lo disponible hoy se suma a lo que hay que comprar, o
       a las tandas de otra elaboracion si el ingrediente es una elaboracion (en cadena).

    filas (todos los insumos): [{'id', 'nombre', 'tipo_medida', 'activo', 'stock', 'a_perder' (vencido o por vencer),
    'vencido' (ya vencido), 'objetivo', 'umbral_bajo', 'umbral_critico', 'proveedor' ({'id','nombre'} o None)}].
    recetas: {id_insumo_producido: {'rinde', 'ingredientes': [(id_insumo, cantidad_por_tanda)]}}.
    costo_de: funcion id_insumo -> costo por unidad base (o None); solo se llama para lo que se compra.
    Devuelve {'comprar': [{'proveedor', 'items', 'total_estimado', 'completo'}], 'producir': [items]}.
    Se compra por proveedor principal (con 'sin proveedor' al final); lo que se elabora se ordena para cocinar primero
    lo que otras elaboraciones usan. A igual orden, por gravedad y nombre."""
    recetas = {k: v for k, v in (recetas or {}).items()}
    datos = {}
    for f in filas:
        stock = max(CERO, a_decimal(f['stock']))
        a_perder = min(max(CERO, a_decimal(f.get('a_perder', CERO))), stock)
        vencido = min(max(CERO, a_decimal(f.get('vencido', CERO))), stock)
        util = stock - a_perder
        estado, porcentaje = estado_de_stock(util, f['objetivo'], f['umbral_bajo'], f['umbral_critico'])
        activo = f.get('activo', True)
        entra = activo and entra_en_reposicion(estado, util, f['objetivo'], todos)
        datos[f['id']] = {
            'fila': f, 'stock': stock, 'a_perder': a_perder, 'util': util, 'estado': estado, 'porcentaje': porcentaje,
            'disponible': stock - vencido,  # lo que se puede usar hoy para cocinar: todo menos lo ya vencido
            'faltante': faltante_a_objetivo(util, f['objetivo']) if entra else CERO,
        }
    recetas = {k: v for k, v in recetas.items() if k in datos}

    consumo = {}        # cuanto van a gastar las producciones planeadas de cada ingrediente
    demandan = {}       # ingrediente -> [(id elaboracion, cantidad)]
    tandas = {}
    tandas_por_objetivo = {}
    for id_producido in orden_elaboraciones(recetas):
        d = datos[id_producido]
        rinde = a_decimal(recetas[id_producido]['rinde'])
        por_objetivo = tandas_para(d['faltante'], rinde) if d['faltante'] > 0 else 0
        falta_consumo = max(CERO, consumo.get(id_producido, CERO) - d['disponible'])
        por_consumo = tandas_para(falta_consumo, rinde) if falta_consumo > 0 else 0
        tandas[id_producido] = max(por_objetivo, por_consumo)
        tandas_por_objetivo[id_producido] = por_objetivo
        if tandas[id_producido] == 0:
            continue
        for id_ingrediente, cantidad in recetas[id_producido]['ingredientes']:
            gasto = a_decimal(cantidad) * tandas[id_producido]
            consumo[id_ingrediente] = consumo.get(id_ingrediente, CERO) + gasto
            demandan.setdefault(id_ingrediente, []).append((id_producido, gasto))

    def nombre_de(id_insumo):
        return datos[id_insumo]['fila']['nombre'] if id_insumo in datos else f'insumo {id_insumo}'

    def base(id_insumo):
        d = datos[id_insumo]
        f = d['fila']
        return {
            'insumo': id_insumo, 'nombre': f['nombre'], 'tipo_medida': f['tipo_medida'], 'estado': d['estado'],
            'porcentaje': d['porcentaje'], 'stock': d['stock'], 'a_perder': d['a_perder'], 'stock_util': d['util'],
            'objetivo': a_decimal(f['objetivo']),
        }

    def quien_necesita(id_insumo):
        return [{'elaboracion': e, 'nombre': nombre_de(e), 'cantidad': c} for e, c in demandan.get(id_insumo, [])]

    comprar = {}
    producir = []
    for id_insumo, d in datos.items():
        f = d['fila']
        if not f.get('activo', True):
            continue
        if id_insumo in recetas:
            t = tandas.get(id_insumo, 0)
            if t == 0:
                continue
            rinde = a_decimal(recetas[id_insumo]['rinde'])
            item = base(id_insumo)
            item.update({
                'faltante': d['faltante'], 'rinde': rinde, 'tandas': t, 'cantidad_a_producir': cuantizar_cantidad(rinde * t),
                'por_objetivo': tandas_por_objetivo[id_insumo] > 0, 'para_elaborar': quien_necesita(id_insumo),
            })
            posibles = None
            faltan = []
            for id_ingrediente, cantidad in sorted(recetas[id_insumo]['ingredientes']):
                cantidad = a_decimal(cantidad)
                disponible = datos[id_ingrediente]['disponible'] if id_ingrediente in datos else CERO
                alcanza = int(disponible // cantidad) if cantidad > 0 else 0
                posibles = alcanza if posibles is None else min(posibles, alcanza)
                necesario = cantidad * t
                if necesario > disponible:
                    faltan.append({
                        'insumo': id_ingrediente, 'nombre': nombre_de(id_ingrediente),
                        'tipo_medida': datos[id_ingrediente]['fila']['tipo_medida'] if id_ingrediente in datos else 'Unidad',
                        'necesario': cuantizar_cantidad(necesario), 'disponible': disponible,
                        'faltante': cuantizar_cantidad(necesario - disponible),
                        'accion': 'producir' if id_ingrediente in recetas else 'comprar',
                    })
            item['tandas_posibles'] = posibles
            item['alcanza'] = not faltan
            item['ingredientes_faltantes'] = faltan
            producir.append(item)
            continue
        falta_consumo = max(CERO, consumo.get(id_insumo, CERO) - d['disponible'])
        cantidad = max(d['faltante'], falta_consumo)
        if cantidad <= 0:
            continue
        item = base(id_insumo)
        costo = costo_de(id_insumo) if costo_de else None
        tiene_costo = costo is not None and a_decimal(costo) > 0
        item.update({
            'faltante': cuantizar_cantidad(cantidad), 'faltante_por_objetivo': d['faltante'],
            'faltante_para_elaborar': cuantizar_cantidad(falta_consumo), 'para_elaborar': quien_necesita(id_insumo),
            'costo_estimado': redondear_dinero(cantidad * a_decimal(costo)) if tiene_costo else None,
        })
        clave = f['proveedor']['id'] if f.get('proveedor') else None
        grupo = comprar.setdefault(clave, {'proveedor': f.get('proveedor'), 'items': []})
        grupo['items'].append(item)

    def gravedad(item):
        return clave_gravedad(item['estado'], item['porcentaje'], item['nombre'])

    memo = {}
    producir.sort(key=lambda i: (profundidad_elaboracion(i['insumo'], recetas, memo),) + gravedad(i))
    grupos = []
    for grupo in comprar.values():
        grupo['items'].sort(key=gravedad)
        total = CERO
        completo = True
        for item in grupo['items']:
            if item['costo_estimado'] is None:
                completo = False
            else:
                total += item['costo_estimado']
        grupo['total_estimado'] = redondear_dinero(total)
        grupo['completo'] = completo
        grupos.append(grupo)
    grupos.sort(key=lambda g: (g['proveedor'] is None, (g['proveedor'] or {}).get('nombre', '').lower()))
    return {'comprar': grupos, 'producir': producir}
