"""Prueba de la linea de tiempo de auditoria (cobros, hito 6) sin base de datos: validacion de los filtros, la frase de cada
tipo de evento y la mezcla ordenada de las distintas fuentes con su paginacion.
Solo libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_auditoria_calculos.py
"""
import importlib.util
import sys
import types
from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path

CARPETA = Path(__file__).resolve().parents[2] / 'restaurante'


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(f'restaurante.{nombre}', CARPETA / f'{nombre}.py')
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[f'restaurante.{nombre}'] = modulo
    spec.loader.exec_module(modulo)
    return modulo


paquete = types.ModuleType('restaurante'); paquete.__path__ = [str(CARPETA)]; sys.modules['restaurante'] = paquete
cargar('comprobante_calculos')
au = cargar('auditoria_calculos')

RESULTADOS = []


def chequear(nombre, obtenido, esperado):
    ok = obtenido == esperado
    RESULTADOS.append(ok)
    print(('OK   ' if ok else 'FALLA'), nombre, '' if ok else f'-> obtenido {obtenido!r}, esperado {esperado!r}')


def invalido(nombre, params, campo):
    try:
        au.validar_filtros(params)
    except au.FiltroInvalido as error:
        chequear(nombre, error.campo, campo)
    except Exception as error:
        chequear(nombre, f'{type(error).__name__}: {error}', f'FiltroInvalido({campo})')
    else:
        chequear(nombre, 'no lanzo nada', f'FiltroInvalido({campo})')


# ---------- filtros ----------
f = au.validar_filtros({})
chequear('sin filtros: limite y desplazamiento por defecto', (f['limite'], f['desplazamiento']), (100, 0))
chequear('sin filtros: todo vacio', (f['desde'], f['hasta'], f['tipos'], f['empleado'], f['mesa'], f['caja'], f['factura'], f['pago']),
         (None,) * 8)
f = au.validar_filtros({'desde': '2026-11-01', 'hasta': '2026-11-08', 'tipo': 'pago, Caja', 'empleado': '3', 'mesa': '5',
                        'caja': '2', 'factura': '9', 'pago': '11', 'limite': '20', 'desplazamiento': '40'})
chequear('filtros completos: fechas', (f['desde'], f['hasta']), (date(2026, 11, 1), date(2026, 11, 8)))
chequear('filtros completos: tipos en minuscula y sin espacios', f['tipos'], ('pago', 'caja'))
chequear('filtros completos: numeros', (f['empleado'], f['mesa'], f['caja'], f['factura'], f['pago'], f['limite'], f['desplazamiento']),
         (3, 5, 2, 9, 11, 20, 40))
chequear('filtros: valores vacios cuentan como ausentes', au.validar_filtros({'desde': '', 'mesa': '', 'tipo': ''})['mesa'], None)
chequear('filtros: un dia solo (desde = hasta)', au.validar_filtros({'desde': '2026-11-08', 'hasta': '2026-11-08'})['desde'], date(2026, 11, 8))
invalido('filtros: fecha mal escrita', {'desde': '08/11/2026'}, 'desde')
invalido('filtros: fecha imposible', {'hasta': '2026-02-30'}, 'hasta')
invalido('filtros: desde posterior a hasta', {'desde': '2026-11-09', 'hasta': '2026-11-08'}, 'desde')
invalido('filtros: tipo desconocido', {'tipo': 'pago,rareza'}, 'tipo')
invalido('filtros: tipo solo comas', {'tipo': ',,'}, 'tipo')
invalido('filtros: mesa no numerica', {'mesa': 'cinco'}, 'mesa')
invalido('filtros: mesa cero', {'mesa': '0'}, 'mesa')
invalido('filtros: empleado negativo', {'empleado': '-1'}, 'empleado')
invalido('filtros: limite cero', {'limite': '0'}, 'limite')
invalido('filtros: limite pasado del maximo', {'limite': '501'}, 'limite')
invalido('filtros: desplazamiento negativo', {'desplazamiento': '-1'}, 'desplazamiento')
invalido('filtros: desplazamiento pasado del maximo', {'desplazamiento': '5001'}, 'desplazamiento')
chequear('filtros: limite maximo entra', au.validar_filtros({'limite': '500'})['limite'], 500)
chequear('filtros: desplazamiento cero entra', au.validar_filtros({'desplazamiento': '0'})['desplazamiento'], 0)
chequear('incluye: sin filtro de tipo entran todos', all(au.incluye(au.validar_filtros({}), t) for t in au.TIPOS), True)
chequear('incluye: solo los pedidos', [t for t in au.TIPOS if au.incluye(au.validar_filtros({'tipo': 'pago,mesa'}), t)], ['pago', 'mesa'])

# ---------- una frase por evento ----------
ana = {'id': 3, 'nombre': 'Ana Gómez'}
t0 = datetime(2026, 11, 8, 20, 30)

e = au.evento_de_pago({'fecha_hora': t0, 'evento': 'Cobrado en efectivo', 'estado_anterior': None, 'estado_nuevo': 'Aprobado',
                       'detalle': 'Recibido USD 10,00', 'empleado': ana, 'mesa': 5, 'factura': 7, 'pago': 11, 'medio': 'Efectivo',
                       'monto': D('12000')})
chequear('pago: frase', e['descripcion'], 'Pago #11 (Efectivo): Cobrado en efectivo (Aprobado). Recibido USD 10,00')
chequear('pago: datos', (e['tipo'], e['evento'], e['mesa'], e['factura'], e['pago'], e['caja'], e['monto'], e['moneda'], e['empleado']),
         ('pago', 'Cobrado en efectivo', 5, 7, 11, None, D('12000'), 'ARS', ana))
e = au.evento_de_pago({'fecha_hora': t0, 'evento': 'Pago anulado', 'estado_anterior': 'Aprobado', 'estado_nuevo': 'Anulado', 'detalle': None,
                       'empleado': None, 'mesa': 5, 'factura': 7, 'pago': 11, 'medio': 'Efectivo', 'monto': D('12000')})
chequear('pago: cambio de estado, sin detalle ni empleado', (e['descripcion'], e['empleado']),
         ('Pago #11 (Efectivo): Pago anulado (Aprobado -> Anulado)', None))
e = au.evento_de_pago({'fecha_hora': t0, 'evento': 'Aviso', 'estado_anterior': 'Pendiente', 'estado_nuevo': 'Pendiente', 'detalle': 'x',
                       'empleado': None, 'mesa': 1, 'factura': 1, 'pago': 1, 'medio': 'Mercado Pago', 'monto': D('1')})
chequear('pago: mismo estado no repite la flecha', e['descripcion'], 'Pago #1 (Mercado Pago): Aviso. x')

e = au.evento_de_movimiento({'fecha_hora': t0, 'tipo': 'Ingreso', 'concepto': 'Venta', 'medio': 'Efectivo', 'moneda': 'USD', 'monto': D('10'),
                             'descripcion': None, 'empleado': ana, 'caja': 2, 'pago': 11, 'mesa': 5, 'factura': 7})
chequear('movimiento: ingreso', e['descripcion'], 'Ingreso de USD 10,00 en caja #2 (Efectivo): Venta del pago #11')
chequear('movimiento: datos', (e['tipo'], e['evento'], e['caja'], e['pago'], e['mesa'], e['monto'], e['moneda']),
         ('movimiento', 'Venta', 2, 11, 5, D('10'), 'USD'))
e = au.evento_de_movimiento({'fecha_hora': t0, 'tipo': 'Egreso', 'concepto': 'Manual', 'medio': 'Efectivo', 'moneda': 'ARS', 'monto': D('1500.5'),
                             'descripcion': 'Compra de hielo', 'empleado': ana, 'caja': 2, 'pago': None, 'mesa': None, 'factura': None})
chequear('movimiento: egreso manual sin pago', e['descripcion'], 'Egreso de $ 1.500,50 en caja #2 (Efectivo): Manual. Compra de hielo')

e = au.evento_de_caja({'caja': 2, 'fecha_hora': t0, 'empleado': ana}, cierre=False)
chequear('caja: apertura', (e['descripcion'], e['evento'], e['caja'], e['tipo']), ('Se abrio la caja #2.', 'Apertura', 2, 'caja'))
e = au.evento_de_caja({'caja': 2, 'fecha_hora': t0, 'empleado': ana, 'esperado': D('50000'), 'declarado': D('49000')}, cierre=True)
chequear('caja: cierre con faltante', e['descripcion'], 'Se cerro la caja #2. Esperado $ 50.000,00, declarado $ 49.000,00, diferencia $ -1.000,00.')
e = au.evento_de_caja({'caja': 2, 'fecha_hora': t0, 'empleado': ana, 'esperado': D('50000'), 'declarado': D('50000')}, cierre=True)
chequear('caja: cierre sin diferencia', e['descripcion'], 'Se cerro la caja #2. Esperado $ 50.000,00, declarado $ 50.000,00, sin diferencia.')
e = au.evento_de_caja({'caja': 2, 'fecha_hora': t0, 'empleado': ana, 'esperado': None, 'declarado': None}, cierre=True)
chequear('caja: cierre sin totales guardados', e['descripcion'], 'Se cerro la caja #2.')

e = au.evento_de_factura({'fecha_hora': t0, 'empleado': ana, 'mesa': 5, 'factura': 7, 'total': D('10000')}, anulacion=False)
chequear('factura: emision', (e['descripcion'], e['evento'], e['monto'], e['moneda']),
         ('Se emitio la factura #7 de la mesa 5 por $ 10.000,00.', 'Emision', D('10000'), 'ARS'))
e = au.evento_de_factura({'fecha_hora': t0, 'empleado': ana, 'mesa': 5, 'factura': 7, 'total': D('10000'), 'motivo': 'Error de carga'}, anulacion=True)
chequear('factura: anulacion con motivo', e['descripcion'], 'Se anulo la factura #7 de la mesa 5 ($ 10.000,00). Motivo: Error de carga.')
e = au.evento_de_factura({'fecha_hora': t0, 'empleado': ana, 'mesa': 5, 'factura': 7, 'total': D('10000'), 'motivo': None}, anulacion=True)
chequear('factura: anulacion sin motivo', e['descripcion'], 'Se anulo la factura #7 de la mesa 5 ($ 10.000,00).')

e = au.evento_de_mesa({'fecha_hora': t0, 'empleado': ana, 'mesa': 5, 'motivo': 'El cliente se fue sin pagar'})
chequear('mesa: cierre forzado', (e['descripcion'], e['evento'], e['mesa'], e['tipo']),
         ('Se cerro la mesa 5 con saldo pendiente. Motivo: El cliente se fue sin pagar.', 'Cierre forzado', 5, 'mesa'))

# ---------- mezcla y paginacion ----------
def ev(minuto, tipo='pago', codigo='x', pago=None, caja=None):
    return {'fecha_hora': datetime(2026, 11, 8, 20, minuto), 'tipo': tipo, 'evento': codigo, 'pago': pago, 'caja': caja}


a = [ev(5, 'pago', 'a1', pago=1), ev(1, 'pago', 'a2', pago=1)]
b = [ev(4, 'movimiento', 'b1'), ev(2, 'movimiento', 'b2')]
c = [ev(3, 'caja', 'c1', caja=1)]
pagina, mas = au.mezclar([a, b, c], 10)
chequear('mezclar: de lo mas nuevo a lo mas viejo', [e['evento'] for e in pagina], ['a1', 'b1', 'c1', 'b2', 'a2'])
chequear('mezclar: no hay mas', mas, False)
pagina, mas = au.mezclar([a, b, c], 2)
chequear('mezclar: primera pagina', ([e['evento'] for e in pagina], mas), (['a1', 'b1'], True))
pagina, mas = au.mezclar([a, b, c], 2, 2)
chequear('mezclar: segunda pagina', ([e['evento'] for e in pagina], mas), (['c1', 'b2'], True))
pagina, mas = au.mezclar([a, b, c], 2, 4)
chequear('mezclar: ultima pagina', ([e['evento'] for e in pagina], mas), (['a2'], False))
pagina, mas = au.mezclar([a, b, c], 5)
chequear('mezclar: justo el tamano de la pagina no marca "hay mas"', (len(pagina), mas), (5, False))
chequear('mezclar: desplazamiento pasado del final', au.mezclar([a, b, c], 5, 100), ([], False))
chequear('mezclar: sin fuentes', au.mezclar([], 5), ([], False))
chequear('mezclar: fuentes vacias', au.mezclar([[], []], 5), ([], False))
iguales = [ev(7, 'pago', 'p', pago=1), ev(7, 'pago', 'p', pago=2), ev(7, 'movimiento', 'm')]
primero, _ = au.mezclar([iguales], 10)
segundo, _ = au.mezclar([list(reversed(iguales))], 10)
chequear('mezclar: el orden con la misma hora no depende de como llegaron', [(e['tipo'], e['pago']) for e in primero], [(e['tipo'], e['pago']) for e in segundo])

total = len(RESULTADOS)
bien = sum(RESULTADOS)
print(f'\n{bien}/{total} verificaciones correctas')
sys.exit(0 if bien == total else 1)
