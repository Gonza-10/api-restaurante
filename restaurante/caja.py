"""Caja: apertura, movimientos de dinero y cierre con arqueo por medio y por moneda.

- Una sola caja abierta a la vez (indice unico UQ_Caja_Abierta). Abren y cierran Admin y Gerente.
- Dos medios: Efectivo (el cajon: ARS, USD, BRL y PYG) y MercadoPago (la cuenta digital, siempre en pesos). Un cobro de
  Mercado Pago se anota en la caja cuando queda APROBADO, con la etiqueta MercadoPago; no pasa por el cajon.
- Todo movimiento se hace con la fila de la Caja BLOQUEADA (select_for_update) dentro de una transaccion: asi dos
  movimientos o un movimiento y un cierre a la vez no se pisan, y el saldo que se chequea es el real.
- `registrar_movimiento` lo usan tambien los cobros (hito 3): el que llama ya tiene la caja bloqueada.
- Los calculos (esperado, diferencia, validaciones) estan en caja_calculos.py.
"""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .caja_calculos import (
    CONCEPTOS, MEDIO_EFECTIVO, MEDIO_MERCADO_PAGO, MEDIOS, TIPOS_MOVIMIENTO,
    arqueo, arqueo_digital, egreso_posible, total_en_pesos, validar_mercado_pago,
)
from .cobros_calculos import CERO, MONEDA_BASE, MONEDAS, convertir_a_ars
from .cotizacion import cotizaciones_vigentes, ultima_cotizacion
from .models import Caja, CajaMoneda, MovimientoCaja, Pago


class ReglaCaja(Exception):
    """Una regla de negocio de la caja impide la operacion (se responde 409). El mensaje esta listo para mostrar."""

    def __init__(self, mensaje, **extra):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.extra = extra


def caja_abierta():
    return Caja.objects.select_related('empleado_apertura').filter(estado='Abierta').first()


def caja_abierta_bloqueada():
    """La caja abierta con su fila bloqueada (solo dentro de transaction.atomic)."""
    return Caja.objects.select_for_update().filter(estado='Abierta').first()


_caja_abierta_bloqueada = caja_abierta_bloqueada


def bloqueos_de_cierre(caja):
    """Motivos que impiden cerrar la caja: un cobro pendiente (Mercado Pago sin resolver) no se puede dejar sin caja."""
    pendientes = Pago.objects.filter(estado='Pendiente').count()
    if pendientes:
        return [f'Hay {pendientes} pago(s) pendiente(s) de resolver.']
    return []


def totales_movimientos(caja):
    """(ingresos_efectivo, egresos_efectivo, ingresos_mp, egresos_mp): los dos primeros {moneda: total}; los otros dos, el
    total en pesos de Mercado Pago."""
    ing, egr = {}, {}
    ing_mp, egr_mp = CERO, CERO
    filas = MovimientoCaja.objects.filter(caja=caja).values('medio', 'moneda', 'tipo').annotate(total=Sum('monto'))
    for fila in filas:
        total = fila['total'] or CERO
        if fila['medio'] == MEDIO_MERCADO_PAGO:
            if fila['tipo'] == 'Ingreso':
                ing_mp += total
            else:
                egr_mp += total
        else:
            destino = ing if fila['tipo'] == 'Ingreso' else egr
            destino[fila['moneda']] = destino.get(fila['moneda'], CERO) + total
    return ing, egr, ing_mp, egr_mp


def _filas(caja):
    return {(f.medio, f.moneda): f for f in CajaMoneda.objects.filter(caja=caja)}


def _apertura_efectivo(filas):
    return {m: filas[(MEDIO_EFECTIVO, m)].monto_apertura for m in MONEDAS if (MEDIO_EFECTIVO, m) in filas}


def resumen_arqueo(caja):
    """Arqueo de la caja: {'efectivo': {moneda: {...}}, 'mercado_pago': {...}, 'total': {...}}.
    Efectivo, por moneda: apertura, ingresos, egresos, esperado y, si esta cerrada, declarado y diferencia.
    Mercado Pago (siempre pesos): ingresos, egresos, esperado y, si esta cerrada, declarado y diferencia.
    Total en pesos (efectivo convertido + Mercado Pago): esperado y declarado; en una caja abierta usa las cotizaciones
    vigentes ahora; en una cerrada, lo que se guardo al cerrar."""
    filas = _filas(caja)
    ing, egr, ing_mp, egr_mp = totales_movimientos(caja)
    cerrada = caja.estado == 'Cerrada'
    declarado = declarado_mp = None
    if cerrada:
        declarado = {m: filas[(MEDIO_EFECTIVO, m)].monto_declarado
                     if (MEDIO_EFECTIVO, m) in filas and filas[(MEDIO_EFECTIVO, m)].monto_declarado is not None else CERO
                     for m in MONEDAS}
        fila_mp = filas.get((MEDIO_MERCADO_PAGO, MONEDA_BASE))
        declarado_mp = fila_mp.monto_declarado if fila_mp and fila_mp.monto_declarado is not None else CERO
    efectivo = arqueo(_apertura_efectivo(filas), ing, egr, declarado)
    digital = arqueo_digital(ing_mp, egr_mp, declarado_mp)

    if cerrada:
        esperado_total = caja.total_esperado_ars
        declarado_total = caja.total_declarado_ars
        total = {
            'esperado_en_pesos': None if esperado_total is None else {
                'efectivo': esperado_total - digital['esperado'], 'mercado_pago': digital['esperado'], 'total': esperado_total},
            'declarado_en_pesos': None if declarado_total is None else {
                'efectivo': declarado_total - digital['declarado'], 'mercado_pago': digital['declarado'], 'total': declarado_total},
        }
    else:
        total = {
            'esperado_en_pesos': total_en_pesos({m: efectivo[m]['esperado'] for m in MONEDAS}, cotizaciones_vigentes(), digital['esperado']),
            'declarado_en_pesos': None,
        }
    return {'efectivo': efectivo, 'mercado_pago': digital, 'total': total}


def cotizacion_para(moneda):
    """ARS por 1 unidad de la moneda: 1 para pesos; la ultima guardada para las demas."""
    if moneda == MONEDA_BASE:
        return Decimal('1')
    fila = ultima_cotizacion(moneda)
    if fila is None:
        raise ReglaCaja(f'Todavia no hay cotizacion de {moneda}. Esperar a que el sistema la consulte al BCRA '
                        '(o usar POST /cotizaciones/actualizar).')
    return fila.valor


def abrir_caja(empleado, montos):
    """Abre la caja con el efectivo inicial de cada moneda (`montos` ya validado: {moneda: Decimal}). Devuelve la Caja."""
    if caja_abierta() is not None:
        raise ReglaCaja('Ya hay una caja abierta. Cerrarla antes de abrir otra.')
    try:
        with transaction.atomic():
            caja = Caja.objects.create(
                empleado_apertura=empleado,
                fecha_hora_apertura=timezone.now(),
                monto_apertura=montos[MONEDA_BASE],
                estado='Abierta',
            )
            CajaMoneda.objects.bulk_create(
                [CajaMoneda(caja=caja, medio=MEDIO_EFECTIVO, moneda=m, monto_apertura=montos[m]) for m in MONEDAS]
                + [CajaMoneda(caja=caja, medio=MEDIO_MERCADO_PAGO, moneda=MONEDA_BASE, monto_apertura=CERO)]
            )
    except IntegrityError:
        # otra apertura simultanea gano: el indice unico de la base lo garantiza
        raise ReglaCaja('Ya hay una caja abierta. Cerrarla antes de abrir otra.')
    return caja


def esperado_actual(caja, moneda):
    """Efectivo que tiene que haber ahora en el cajon en esa moneda."""
    return resumen_arqueo(caja)['efectivo'][moneda]['esperado']


def registrar_movimiento(caja, tipo, concepto, moneda, monto, empleado, descripcion=None, pago=None,
                         controlar_saldo=True, medio=MEDIO_EFECTIVO):
    """Anota un movimiento en una caja YA BLOQUEADA y abierta (el que llama abre la transaccion y bloquea la fila).
    Guarda la cotizacion vigente y el equivalente en pesos. Un egreso de efectivo no puede dejar el cajon en negativo
    (`controlar_saldo=False` lo permite, por ejemplo para contramovimientos de anulaciones).
    `medio=MercadoPago`: el cobro aprobado por Mercado Pago (solo ingresos y solo en pesos); no toca el cajon."""
    if tipo not in TIPOS_MOVIMIENTO:
        raise ValueError(f'Tipo de movimiento invalido: {tipo}')
    if concepto not in CONCEPTOS:
        raise ValueError(f'Concepto invalido: {concepto}')
    if medio not in MEDIOS:
        raise ValueError(f'Medio invalido: {medio}')
    if medio == MEDIO_MERCADO_PAGO and (moneda != MONEDA_BASE or tipo != 'Ingreso'):
        raise ValueError('Mercado Pago solo registra ingresos en pesos.')
    if caja.estado != 'Abierta':
        raise ReglaCaja('La caja esta cerrada.')
    if tipo == 'Egreso' and controlar_saldo and medio == MEDIO_EFECTIVO:
        disponible = esperado_actual(caja, moneda)
        if not egreso_posible(disponible, monto):
            raise ReglaCaja(
                f'No alcanza el efectivo en {moneda}: hay {disponible} y se quieren sacar {monto}.',
                disponible=str(disponible), moneda=moneda,
            )
    cotizacion = cotizacion_para(moneda)
    monto_ars = monto if moneda == MONEDA_BASE else convertir_a_ars(monto, cotizacion)
    return MovimientoCaja.objects.create(
        caja=caja, tipo=tipo, concepto=concepto, medio=medio, moneda=moneda, monto=monto, cotizacion=cotizacion,
        monto_ars=monto_ars, descripcion=descripcion, fecha_hora=timezone.now(), empleado=empleado, pago=pago,
    )


def registrar_movimiento_manual(empleado, tipo, moneda, monto, descripcion):
    """Ingreso o egreso de EFECTIVO cargado a mano por Admin/Gerente en la caja abierta."""
    with transaction.atomic():
        caja = _caja_abierta_bloqueada()
        if caja is None:
            raise ReglaCaja('No hay una caja abierta.')
        return registrar_movimiento(caja, tipo, 'Manual', moneda, monto, empleado, descripcion=descripcion)


def cerrar_caja(empleado, declarado, mercado_pago=None):
    """Cierra la caja con lo contado en cada moneda (`declarado` ya validado: las cuatro monedas) y lo acreditado en la
    cuenta de Mercado Pago (`mercado_pago`: obligatorio si el sistema registro cobros digitales). Guarda esperado,
    contado y diferencia de cada medio y el total en pesos. Una diferencia no impide cerrar: queda registrada.
    Si el monto de Mercado Pago es invalido o falta, levanta CajaInvalida. Devuelve la Caja cerrada."""
    with transaction.atomic():
        caja = _caja_abierta_bloqueada()
        if caja is None:
            raise ReglaCaja('No hay una caja abierta.')
        motivos = bloqueos_de_cierre(caja)
        if motivos:
            raise ReglaCaja('No se puede cerrar la caja: ' + ' '.join(motivos), motivos=motivos)
        filas = _filas(caja)
        ing, egr, ing_mp, egr_mp = totales_movimientos(caja)
        digital_esperado = arqueo_digital(ing_mp, egr_mp)['esperado']
        declarado_mp = validar_mercado_pago(mercado_pago, digital_esperado)   # CajaInvalida si falta
        calculo = arqueo(_apertura_efectivo(filas), ing, egr, declarado)
        digital = arqueo_digital(ing_mp, egr_mp, declarado_mp)
        for moneda in MONEDAS:
            fila = calculo[moneda]
            CajaMoneda.objects.filter(caja=caja, medio=MEDIO_EFECTIVO, moneda=moneda).update(
                monto_esperado=fila['esperado'], monto_declarado=fila['declarado'], diferencia=fila['diferencia'],
            )
        if (MEDIO_MERCADO_PAGO, MONEDA_BASE) in filas:
            CajaMoneda.objects.filter(caja=caja, medio=MEDIO_MERCADO_PAGO, moneda=MONEDA_BASE).update(
                monto_esperado=digital['esperado'], monto_declarado=digital['declarado'], diferencia=digital['diferencia'],
            )
        else:   # caja abierta antes de que existiera el medio Mercado Pago
            CajaMoneda.objects.create(
                caja=caja, medio=MEDIO_MERCADO_PAGO, moneda=MONEDA_BASE, monto_apertura=CERO,
                monto_esperado=digital['esperado'], monto_declarado=digital['declarado'], diferencia=digital['diferencia'],
            )
        cotizaciones = cotizaciones_vigentes()
        total_esp = total_en_pesos({m: calculo[m]['esperado'] for m in MONEDAS}, cotizaciones, digital['esperado'])
        total_decl = total_en_pesos(declarado, cotizaciones, declarado_mp)
        Caja.objects.filter(pk=caja.pk).update(
            estado='Cerrada',
            fecha_hora_cierre=timezone.now(),
            empleado_cierre=empleado,
            monto_cierre=declarado[MONEDA_BASE],
            total_esperado_ars=None if total_esp is None else total_esp['total'],
            total_declarado_ars=None if total_decl is None else total_decl['total'],
        )
    return Caja.objects.select_related('empleado_apertura', 'empleado_cierre').get(pk=caja.pk)
