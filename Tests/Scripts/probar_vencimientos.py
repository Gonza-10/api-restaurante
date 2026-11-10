"""Prueba de los vencimientos contra la base de verdad (hito 6): el baja automatica de lotes vencidos al abrir la jornada.

La API no deja cargar un lote con fecha pasada, asi que este script crea los lotes vencidos directo en la base (con el ORM
de Django) y despues prueba lo que pasa al abrir la jornada: los vencidos se dan de baja como perdida con motivo
'vencimiento', al costo real del lote; el lote que todavia no vencio no se toca; y se recuerdan los dias que faltan.
NO abre ninguna jornada: llama a la misma funcion que usa la apertura. Al final deja su insumo de prueba dado de baja.

Tambien prueba (hito 6.1) los dias de aviso propios de un insumo y que la lista de reposicion no cuente como stock lo
que se va a perder.

Uso (PowerShell, con el entorno virtual activo, en la raiz del proyecto; no hace falta tener nada corriendo):
    python Tests\\Scripts\\probar_vencimientos.py
"""
import os
import sys
import time
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from restaurante.models import Empleado, Insumo, LoteInsumo, MovimientoStock, Perdida  # noqa: E402
from restaurante.notificaciones import armar_notificaciones  # noqa: E402
from restaurante.reposicion import armar_reposicion  # noqa: E402
from restaurante.stock import dar_baja_lote, inconsistencias_del_libro, stock_actual  # noqa: E402
from restaurante.vencimientos import armar_vencimientos, dias_aviso, vencimientos_al_abrir  # noqa: E402

RESULTADOS = []


def chequear(nombre, obtenido, esperado):
    ok = obtenido == esperado
    RESULTADOS.append(ok)
    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}" + ('' if ok else f'\n         esperado: {esperado!r}\n         obtenido: {obtenido!r}'))


def crear_lote(insumo, dias, cantidad, costo):
    ahora = timezone.now()
    lote = LoteInsumo.objects.create(
        insumo=insumo, compra=None, origen='Ajuste', fecha_ingreso=ahora,
        fecha_vencimiento=timezone.localdate() + timedelta(days=dias),
        cantidad_inicial=cantidad, cantidad_actual=cantidad, costo_unitario=costo, estado='Activo',
    )
    MovimientoStock.objects.create(
        lote=lote, tipo='Ajuste', cantidad=cantidad, fecha_hora=ahora, empleado=None, motivo='Prueba de vencimientos',
    )
    return lote


gerente = Empleado.objects.filter(rol__nombre='Gerente', activo=True).first()
if gerente is None:
    print('No hay un Gerente activo en la base: cargar 99_Seed_AE4.sql.')
    sys.exit(2)

insumo = Insumo.objects.create(
    nombre=f'ZZ Venc Prueba {int(time.time())}', tipo_medida='Masa', stock_objetivo=1000, activo=True,
    umbral_bajo_pct=50, umbral_critico_pct=20,
)
print(f'Insumo de prueba: {insumo.nombre} (id {insumo.id})')

ayer = crear_lote(insumo, -1, D('500'), D('0.01'))       # vencio ayer
antes = crear_lote(insumo, -2, D('400'), D('0.02'))      # vencio hace 2 dias
vigente = crear_lote(insumo, 2, D('300'), D('0.03'))     # vence en 2 dias
sin_fecha = LoteInsumo.objects.create(                  # sin vencimiento: nunca se avisa ni se da de baja
    insumo=insumo, compra=None, origen='Ajuste', fecha_ingreso=timezone.now(), fecha_vencimiento=None,
    cantidad_inicial=D('100'), cantidad_actual=D('100'), costo_unitario=D('0.01'), estado='Activo',
)
MovimientoStock.objects.create(
    lote=sin_fecha, tipo='Ajuste', cantidad=D('100'), fecha_hora=timezone.now(), empleado=None, motivo='Prueba de vencimientos'
)

print('Antes de abrir la jornada')
chequear('el stock cuenta todos los lotes activos (500 + 400 + 300 + 100)', stock_actual(insumo.id), D('1300'))
resumen = armar_vencimientos(ve_costos=True)
mios = {f['lote']: f for f in resumen['vencidos'] + resumen['por_vencer'] if f['insumo'] == insumo.id}
chequear('los dos vencidos y el vigente aparecen; el que no tiene fecha, no', sorted(mios), sorted([ayer.id, antes.id, vigente.id]))
chequear('textos de los dias', [mios[ayer.id]['texto'], mios[antes.id]['texto'], mios[vigente.id]['texto']],
         ['vencio ayer', 'vencio hace 2 dias', 'vence en 2 dias'])
chequear('estados', [mios[ayer.id]['estado'], mios[vigente.id]['estado']], ['vencido', 'por_vencer'])
nots = [n for n in armar_notificaciones()['notificaciones'] if n['tipo'].startswith('lote_') and n['lote']['insumo'] == insumo.id]
chequear('notificaciones: 2 lotes vencidos urgentes y 1 por vencer', sorted((n['tipo'], n['severidad']) for n in nots),
         [('lote_por_vencer', 'aviso'), ('lote_vencido', 'urgente'), ('lote_vencido', 'urgente')])

print('Dias de aviso propios del insumo (el lote vigente vence en 2 dias)')
general = dias_aviso()
for propios, esperado_estado, esperado_ventana in ((1, None, 1), (2, 'por_vencer', 2), (0, None, 0), (None, 'por_vencer', general)):
    insumo.dias_aviso_vencimiento = propios
    insumo.save(update_fields=['dias_aviso_vencimiento'])
    r = armar_vencimientos(ve_costos=True)
    filas = {f['lote']: f for f in r['vencidos'] + r['por_vencer'] if f['insumo'] == insumo.id}
    nombre = 'usa los generales' if propios is None else f'propios: {propios}'
    chequear(f'aviso {nombre}: el lote vigente {"se avisa" if esperado_estado else "no se avisa todavia"}',
             filas[vigente.id]['estado'] if vigente.id in filas else None, esperado_estado)
    chequear(f'aviso {nombre}: los vencidos aparecen igual', (ayer.id in filas, antes.id in filas), (True, True))
    if esperado_estado:
        chequear(f'aviso {nombre}: la fila dice con cuantos dias se avisa', (filas[vigente.id]['dias_aviso'], filas[vigente.id]['aviso_propio']),
                 (esperado_ventana, propios is not None))

print('Al abrir la jornada')
resultado = vencimientos_al_abrir(gerente)
bajas = {f['lote']: f for f in resultado['dados_de_baja']['lotes'] if f['insumo'] == insumo.id}
chequear('se dan de baja los dos vencidos, y solo esos', sorted(bajas), sorted([ayer.id, antes.id]))
chequear('valor a costo real de cada lote: 500 x 0,01 y 400 x 0,02', (bajas[ayer.id]['valor'], bajas[antes.id]['valor']), (D('5.00'), D('8.00')))
for lote in (ayer, antes, vigente, sin_fecha):
    lote.refresh_from_db()
chequear('los vencidos quedan en Vencido y en cero', [(l.estado, l.cantidad_actual) for l in (ayer, antes)], [('Vencido', D('0')), ('Vencido', D('0'))])
chequear('el vigente y el que no vence no se tocan', [(l.estado, l.cantidad_actual) for l in (vigente, sin_fecha)],
         [('Activo', D('300')), ('Activo', D('100'))])
chequear('el stock ahora es 400', stock_actual(insumo.id), D('400'))
perdidas = list(Perdida.objects.filter(insumo=insumo).order_by('id'))
chequear('quedaron 2 perdidas de insumo con motivo vencimiento', sorted((p.alcance, p.motivo, p.cantidad) for p in perdidas),
         sorted([('Insumo', 'vencimiento', D('500')), ('Insumo', 'vencimiento', D('400'))]))
chequear('se procesan primero los que vencieron antes (el de hace 2 dias, 400)', [p.cantidad for p in perdidas], [D('400'), D('500')])
chequear('registradas a nombre de quien abrio la jornada', {p.empleado_id for p in perdidas}, {gerente.id})
movimientos = list(MovimientoStock.objects.filter(perdida__in=perdidas).order_by('id'))
chequear('en el libro: un movimiento Vencido negativo por perdida', sorted((m.tipo, m.cantidad) for m in movimientos),
         sorted([('Vencido', D('-500')), ('Vencido', D('-400'))]))
chequear('el libro sigue consistente (suma de movimientos = cantidad de cada lote)',
         [m for m in inconsistencias_del_libro() if m['insumo'] == insumo.id], [])
por_vencer = [f for f in resultado['por_vencer'] if f['insumo'] == insumo.id]
chequear('se recuerda el vigente con los dias que faltan', [(f['lote'], f['dias_restantes']) for f in por_vencer], [(vigente.id, 2)])
chequear('y hay un aviso listo para mostrar', any(insumo.nombre in a and 'vence en 2 dias' in a for a in resultado['avisos']), True)

print('Reposicion: lo que se va a perder no cuenta como stock')


def fila_reposicion():
    plan = armar_reposicion()
    return next((i for g in plan['comprar'] for i in g['items'] if i['insumo'] == insumo.id), None)


r = fila_reposicion()
chequear('con el aviso general, el lote vigente (300 que vence en 2 dias) no cuenta: de 400 hay 100 utiles (10 %), se piden 900',
         (r['stock'], r['a_perder'], r['stock_util'], r['estado'], r['faltante']), (D('400'), D('300'), D('100'), 'Critico', D('900')))
insumo.dias_aviso_vencimiento = 1
insumo.save(update_fields=['dias_aviso_vencimiento'])
r = fila_reposicion()
chequear('si el insumo avisa con 1 dia, el vigente todavia cuenta: 400 utiles (40 %), se piden 600',
         (r['a_perder'], r['stock_util'], r['estado'], r['faltante']), (D('0'), D('400'), 'Bajo', D('600')))
insumo.dias_aviso_vencimiento = None
insumo.save(update_fields=['dias_aviso_vencimiento'])

print('Abrir otra vez no repite las bajas')
otra = vencimientos_al_abrir(gerente)
chequear('ya no hay vencidos de este insumo', [f for f in otra['dados_de_baja']['lotes'] if f['insumo'] == insumo.id], [])
chequear('sigue habiendo solo 2 perdidas', Perdida.objects.filter(insumo=insumo).count(), 2)

# limpieza: lo que queda se da de baja y el insumo de prueba se desactiva
for lote in (vigente, sin_fecha):
    dar_baja_lote(lote.id, gerente, 'Limpieza de la prueba de vencimientos', 'otro')
insumo.activo = False
insumo.save(update_fields=['activo'])
print(f'Limpieza: el insumo de prueba (id {insumo.id}) quedo dado de baja y sin stock.')

ok = sum(RESULTADOS)
print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
sys.exit(0 if ok == len(RESULTADOS) else 1)
