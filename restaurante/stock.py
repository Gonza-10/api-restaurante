"""Operaciones de stock sobre la base de datos: compras, bajas, ajustes y descuento por FEFO.

Reglas que se cumplen aca (y las refuerza la base con CHECK):
- Todo cambio en la cantidad de un lote deja una fila en MovimientoStock (el libro nunca se edita ni se borra).
- Se descuenta siempre del lote que vence antes (FEFO); los que no vencen, al final.
- Cada operacion corre en UNA transaccion y bloquea los lotes que toca: dos operaciones simultaneas sobre el mismo
  insumo se ordenan, y no existe stock negativo.
"""
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Case, IntegerField, Sum, Value, When
from django.utils import timezone

from .jornadas import jornada_abierta
from .models import Compra, LoteInsumo, MovimientoStock, Perdida
from .stock_calculos import CERO, MOTIVO_OTRO, MOTIVO_VENCIMIENTO, costo_unitario, repartir_fefo


class StockInsuficiente(Exception):
    """No alcanza el stock para descontar lo pedido. Nada se modifica."""

    def __init__(self, insumo, pedido, disponible):
        super().__init__(f'Stock insuficiente de {insumo.nombre}.')
        self.insumo = insumo
        self.pedido = pedido
        self.disponible = disponible


def _recalcular_platos(ids_insumo):
    """Despues de cualquier cambio de stock se recalcula que platos se pueden ofrecer. Import tardio: recetas
    importa este modulo."""
    from .recetas import recalcular_al_confirmar
    recalcular_al_confirmar(ids_insumo=list(ids_insumo))


class LoteNoActivo(Exception):
    """El lote ya estaba agotado, vencido o dado de baja."""


def _id_jornada_actual():
    jornada = jornada_abierta()
    return jornada.id if jornada else None


def lotes_fefo(id_insumo, bloquear=False):
    """Lotes activos con stock de un insumo, en orden FEFO: el que vence antes primero, los que no vencen al final,
    y a igual vencimiento el que entro antes. bloquear=True los bloquea hasta terminar la transaccion."""
    consulta = (
        LoteInsumo.objects.filter(insumo_id=id_insumo, estado='Activo', cantidad_actual__gt=0)
        .annotate(_sin_vencimiento=Case(
            When(fecha_vencimiento__isnull=True, then=Value(1)), default=Value(0), output_field=IntegerField()
        ))
        .order_by('_sin_vencimiento', 'fecha_vencimiento', 'fecha_ingreso', 'id')
    )
    if bloquear:
        consulta = consulta.select_for_update()
    return list(consulta)


def stock_actual(id_insumo):
    """Suma de los lotes activos de un insumo."""
    return LoteInsumo.objects.filter(insumo_id=id_insumo, estado='Activo').aggregate(total=Sum('cantidad_actual'))['total'] or CERO


def ultimo_costo(id_insumo):
    """Costo de reposicion: el costo por unidad base del ultimo lote que entro por compra o por elaboracion propia
    (0 si nunca entro uno)."""
    costo = (
        LoteInsumo.objects.filter(insumo_id=id_insumo, origen__in=('Compra', 'Elaboracion'))
        .order_by('-fecha_ingreso', '-id').values_list('costo_unitario', flat=True).first()
    )
    return costo if costo is not None else CERO


def descontar_fefo(
    insumo, cantidad, tipo, empleado=None, id_jornada=None, id_comanda=None, motivo=None, nota=None, id_perdida=None,
    id_produccion=None,
):
    """Descuenta `cantidad` (positiva) del insumo, por FEFO, y deja un movimiento por cada lote tocado.
    Lanza StockInsuficiente (sin modificar nada) si no alcanza. Es la base del consumo por comandas, las perdidas
    y los ajustes negativos. id_perdida enlaza los movimientos con la perdida registrada (hito 4) e id_produccion con la
    elaboracion que los consumio (hito 6)."""
    cantidad = Decimal(cantidad)
    if cantidad <= 0:
        raise ValueError('La cantidad a descontar debe ser mayor que cero.')
    with transaction.atomic():
        lotes = lotes_fefo(insumo.id, bloquear=True)
        tomas, faltante = repartir_fefo([(lote.id, lote.cantidad_actual) for lote in lotes], cantidad)
        if faltante > 0:
            raise StockInsuficiente(insumo, cantidad, cantidad - faltante)
        por_id = {lote.id: lote for lote in lotes}
        ahora = timezone.now()
        movimientos = []
        for id_lote, tomar in tomas:
            lote = por_id[id_lote]
            lote.cantidad_actual -= tomar
            if lote.cantidad_actual == 0:
                lote.estado = 'Agotado'
            lote.save(update_fields=['cantidad_actual', 'estado'])
            movimientos.append(MovimientoStock.objects.create(
                lote=lote, tipo=tipo, cantidad=-tomar, fecha_hora=ahora, empleado=empleado,
                jornada_id=id_jornada, comanda_id=id_comanda, motivo=motivo, nota=nota, perdida_id=id_perdida,
                produccion_id=id_produccion,
            ))
        return movimientos


def devolver_comanda(id_comanda, empleado=None, id_jornada=None, motivo=None):
    """Devuelve al stock lo que consumio una comanda que se cancela: un movimiento 'Devolucion' por cada lote que se toco, con lo
    que todavia no se habia devuelto (cancelar dos veces nunca devuelve de mas). Un lote vencido o dado de baja no recupera nada
    (esa mercaderia ya se desecho). Devuelve la lista de movimientos creados."""
    from .comensales_calculos import plan_devolucion
    with transaction.atomic():
        movimientos = list(
            MovimientoStock.objects.filter(comanda_id=id_comanda, tipo__in=('Consumo', 'Devolucion'))
            .values_list('lote_id', 'tipo', 'cantidad')
        )
        plan = plan_devolucion(movimientos)
        if not plan:
            return []
        lotes = {lote.id: lote for lote in LoteInsumo.objects.select_for_update().filter(id__in=plan.keys()).order_by('id')}
        ahora = timezone.now()
        creados = []
        insumos = set()
        for id_lote in sorted(plan):
            lote = lotes.get(id_lote)
            if lote is None or lote.estado not in ('Activo', 'Agotado'):
                continue
            lote.cantidad_actual += plan[id_lote]
            lote.estado = 'Activo'
            lote.save(update_fields=['cantidad_actual', 'estado'])
            creados.append(MovimientoStock.objects.create(
                lote=lote, tipo='Devolucion', cantidad=plan[id_lote], fecha_hora=ahora, empleado=empleado,
                jornada_id=id_jornada, comanda_id=id_comanda, motivo=(motivo or 'Comanda cancelada')[:100],
            ))
            insumos.add(lote.insumo_id)
        if insumos:
            _recalcular_platos(insumos)   # los platos que se habian quedado sin insumos vuelven a ofrecerse
        return creados


def registrar_compra(proveedor, empleado, lineas, numero_comprobante=None, nota=None):
    """Registra una compra: la cabecera, un lote por linea y un movimiento 'Compra' por lote, todo o nada.
    lineas: [{'insumo', 'cantidad', 'tamano_presentacion', 'cantidad_presentaciones', 'costo_total', 'fecha_vencimiento'}]
    con `cantidad` ya calculada en unidad base."""
    with transaction.atomic():
        ahora = timezone.now()
        compra = Compra.objects.create(
            proveedor=proveedor, fecha_hora=ahora, empleado=empleado, jornada_id=_id_jornada_actual(),
            numero_comprobante=numero_comprobante, nota=nota,
        )
        for linea in lineas:
            cantidad = linea['cantidad']
            lote = LoteInsumo.objects.create(
                insumo=linea['insumo'], compra=compra, origen='Compra', fecha_ingreso=ahora,
                fecha_vencimiento=linea.get('fecha_vencimiento'),
                tamano_presentacion=linea.get('tamano_presentacion'),
                cantidad_presentaciones=linea.get('cantidad_presentaciones'),
                cantidad_inicial=cantidad, cantidad_actual=cantidad,
                costo_unitario=costo_unitario(linea['costo_total'], cantidad), estado='Activo',
            )
            MovimientoStock.objects.create(
                lote=lote, tipo='Compra', cantidad=cantidad, fecha_hora=ahora, empleado=empleado,
                jornada_id=compra.jornada_id,
            )
        _recalcular_platos({linea['insumo'].id for linea in lineas})
        return compra


def dar_baja_lote(id_lote, empleado, motivo, motivo_codigo=None):
    """Da de baja un lote activo: lo que quedaba sale del stock con un movimiento y queda registrado como una
    Perdida de insumo (hito 4). `motivo` es el texto que explica la baja (queda en la nota); `motivo_codigo` es el de
    la lista cerrada y, si no se indica, es 'vencimiento' cuando el lote ya vencio y 'otro' en los demas casos.
    El lote queda 'Vencido' si ya vencio o 'Baja' si no. Lanza LoteNoActivo si ya no estaba activo."""
    with transaction.atomic():
        lote = LoteInsumo.objects.select_for_update().get(pk=id_lote)
        if lote.estado != 'Activo':
            raise LoteNoActivo(f'El lote ya esta en estado {lote.estado}.')
        vencido = lote.fecha_vencimiento is not None and lote.fecha_vencimiento < timezone.localdate()
        if motivo_codigo is None:
            motivo_codigo = MOTIVO_VENCIMIENTO if vencido else MOTIVO_OTRO
        if lote.cantidad_actual > 0:
            ahora = timezone.now()
            id_jornada = _id_jornada_actual()
            perdida = Perdida.objects.create(
                fecha_hora=ahora, empleado=empleado, jornada_id=id_jornada, alcance='Insumo', insumo_id=lote.insumo_id,
                cantidad=lote.cantidad_actual, motivo=motivo_codigo, nota=motivo,
            )
            MovimientoStock.objects.create(
                lote=lote, tipo='Vencido' if motivo_codigo == MOTIVO_VENCIMIENTO else 'Perdida',
                cantidad=-lote.cantidad_actual, fecha_hora=ahora, empleado=empleado, jornada_id=id_jornada,
                motivo=motivo, perdida=perdida,
            )
            lote.cantidad_actual = CERO
        lote.estado = 'Vencido' if vencido else 'Baja'
        lote.save(update_fields=['cantidad_actual', 'estado'])
        _recalcular_platos([lote.insumo_id])
        return lote


def ajustar_stock(insumo, cantidad_real, empleado, motivo):
    """Ajuste por inventario: deja el stock del insumo en `cantidad_real` (lo que se conto en el estante).
    Si hay menos que en el sistema se descuenta por FEFO; si hay mas, se crea un lote de origen 'Ajuste' con el
    costo del ultimo lote comprado. Devuelve (stock_anterior, diferencia, movimientos)."""
    cantidad_real = Decimal(cantidad_real)
    with transaction.atomic():
        lotes = lotes_fefo(insumo.id, bloquear=True)
        anterior = sum((lote.cantidad_actual for lote in lotes), CERO)
        diferencia = cantidad_real - anterior
        if diferencia == 0:
            return anterior, diferencia, []
        id_jornada = _id_jornada_actual()
        _recalcular_platos([insumo.id])
        if diferencia < 0:
            movimientos = descontar_fefo(
                insumo, -diferencia, 'Ajuste', empleado=empleado, id_jornada=id_jornada, motivo=motivo
            )
            return anterior, diferencia, movimientos
        ahora = timezone.now()
        lote = LoteInsumo.objects.create(
            insumo=insumo, compra=None, origen='Ajuste', fecha_ingreso=ahora, fecha_vencimiento=None,
            cantidad_inicial=diferencia, cantidad_actual=diferencia, costo_unitario=ultimo_costo(insumo.id), estado='Activo',
        )
        movimiento = MovimientoStock.objects.create(
            lote=lote, tipo='Ajuste', cantidad=diferencia, fecha_hora=ahora, empleado=empleado,
            jornada_id=id_jornada, motivo=motivo,
        )
        return anterior, diferencia, [movimiento]


def inconsistencias_del_libro():
    """Verifica la regla del libro: la suma de los movimientos de cada lote tiene que ser igual a su cantidad actual.
    Devuelve la lista de lotes que no cumplen (vacia = todo consistente)."""
    sumas = {
        fila['lote_id']: fila['suma']
        for fila in MovimientoStock.objects.values('lote_id').annotate(suma=Sum('cantidad')).order_by()
    }
    malos = []
    for lote in LoteInsumo.objects.values('id', 'insumo_id', 'cantidad_actual').order_by('id'):
        suma = sumas.get(lote['id'], CERO)
        if suma != lote['cantidad_actual']:
            malos.append({
                'lote': lote['id'], 'insumo': lote['insumo_id'],
                'cantidad_actual': str(lote['cantidad_actual']), 'suma_movimientos': str(suma),
            })
    return malos


# ---------- InsumoProveedor (tabla sin columna Id: se maneja con SQL directo) ----------

def proveedores_por_insumo(ids_insumo):
    """{id_insumo: [{'id', 'nombre', 'es_principal'}, ...]} con el principal primero."""
    ids_insumo = list(ids_insumo)
    resultado = {id_insumo: [] for id_insumo in ids_insumo}
    if not ids_insumo:
        return resultado
    marcadores = ','.join(['%s'] * len(ids_insumo))
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT ip.IdInsumo, p.Id, p.Nombre, ip.EsPrincipal FROM dbo.InsumoProveedor ip '
            f'JOIN dbo.Proveedor p ON p.Id = ip.IdProveedor WHERE ip.IdInsumo IN ({marcadores}) '
            'ORDER BY ip.EsPrincipal DESC, p.Nombre',
            ids_insumo,
        )
        for id_insumo, id_proveedor, nombre, es_principal in cursor.fetchall():
            resultado[id_insumo].append({'id': id_proveedor, 'nombre': nombre, 'es_principal': bool(es_principal)})
    return resultado


def fijar_proveedores_de_insumo(id_insumo, items):
    """Reemplaza los proveedores de un insumo. items: [(id_proveedor, es_principal), ...]."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM dbo.InsumoProveedor WHERE IdInsumo = %s', [id_insumo])
            for id_proveedor, es_principal in items:
                cursor.execute(
                    'INSERT INTO dbo.InsumoProveedor (IdInsumo, IdProveedor, EsPrincipal) VALUES (%s, %s, %s)',
                    [id_insumo, id_proveedor, 1 if es_principal else 0],
                )
