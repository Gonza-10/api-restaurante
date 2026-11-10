"""Prueba de restaurante/caja.py con dobles (sin Django ni base): modelos en memoria.
Sirve para comprobar las reglas de negocio; NO reemplaza probar contra SQL Server (bloqueos, restricciones, indices)."""
import os, sys, types, contextlib, datetime
from decimal import Decimal as D
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # raiz del repo
sys.path.insert(0, REPO)

# ---- stubs de django ----
class IntegrityError(Exception): pass
class _Tx:
    @contextlib.contextmanager
    def atomic(self): yield
django = types.ModuleType('django'); dj_db = types.ModuleType('django.db'); dj_models = types.ModuleType('django.db.models')
dj_utils = types.ModuleType('django.utils'); dj_tz = types.ModuleType('django.utils.timezone')
dj_db.IntegrityError = IntegrityError; dj_db.transaction = _Tx()
class Sum:
    def __init__(self, campo): self.campo = campo
dj_models.Sum = Sum
dj_tz.now = lambda: datetime.datetime(2026, 11, 6, 12, 0)
dj_utils.timezone = dj_tz
for n, m in [('django', django), ('django.db', dj_db), ('django.db.models', dj_models), ('django.utils', dj_utils), ('django.utils.timezone', dj_tz)]:
    sys.modules[n] = m
dj_db.models = dj_models

# ---- modelos en memoria ----
class QS(list):
    def __init__(self, items, modelo): super().__init__(items); self.modelo = modelo
    def select_related(self, *a): return self
    def select_for_update(self): return self
    def first(self): return self[0] if self else None
    def count(self): return len(self)
    def filter(self, **kw):
        res = []
        for o in self:
            ok = True
            for k, v in kw.items():
                if k == 'pk': ok &= o.id == v
                elif k == 'caja': ok &= o.caja_id == v.id
                else: ok &= getattr(o, k) == v
            if ok: res.append(o)
        return QS(res, self.modelo)
    def update(self, **kw):
        for o in self:
            for k, v in kw.items(): setattr(o, k, v)
        return len(self)
    def get(self, pk): return self.filter(pk=pk)[0]
    def values(self, *c): self._vals = c; return self
    def annotate(self, **kw):
        (alias, suma), = kw.items(); grupos = {}
        for o in self:
            k = tuple(getattr(o, c) for c in self._vals); grupos[k] = grupos.get(k, D(0)) + getattr(o, suma.campo)
        return [dict(zip(self._vals, k), **{alias: v}) for k, v in grupos.items()]

class Manager:
    def __init__(self, modelo): self.modelo = modelo; self.items = []
    def _qs(self): return QS(self.items, self.modelo)
    def __getattr__(self, n): return getattr(self._qs(), n)
    def create(self, **kw):
        o = self.modelo(**kw); o.id = len(self.items) + 1; self.items.append(o)
        if 'caja' in kw: o.caja_id = kw['caja'].id
        return o
    def bulk_create(self, objs):
        for o in objs:
            o.id = len(self.items) + 1; o.caja_id = o.caja.id; self.items.append(o)

def modelo(nombre, defaults):
    class M:
        def __init__(self, **kw):
            for k, v in defaults.items(): setattr(self, k, v)
            for k, v in kw.items(): setattr(self, k, v)
    M.pk = property(lambda self: self.id)
    M.__name__ = nombre; M.objects = Manager(M); return M
Caja = modelo('Caja', dict(estado='Abierta', fecha_hora_cierre=None, empleado_cierre=None, monto_cierre=None, total_esperado_ars=None, total_declarado_ars=None))
CajaMoneda = modelo('CajaMoneda', dict(medio='Efectivo', monto_esperado=None, monto_declarado=None, diferencia=None, monto_apertura=D(0)))
MovimientoCaja = modelo('MovimientoCaja', dict(pago=None, descripcion=None, medio='Efectivo'))
Pago = modelo('Pago', dict(estado='Aprobado'))
pkg = types.ModuleType('restaurante'); pkg.__path__ = [REPO + '/restaurante']; sys.modules['restaurante'] = pkg
models = types.ModuleType('restaurante.models'); models.Caja, models.CajaMoneda, models.MovimientoCaja, models.Pago = Caja, CajaMoneda, MovimientoCaja, Pago
sys.modules['restaurante.models'] = models
cot = types.ModuleType('restaurante.cotizacion')
COT = {'USD': D('1500'), 'BRL': D('280'), 'PYG': D('0.2388')}
cot.ultima_cotizacion = lambda m: types.SimpleNamespace(valor=COT[m]) if m in COT else None
cot.cotizaciones_vigentes = lambda: dict(COT)
sys.modules['restaurante.cotizacion'] = cot

from restaurante import caja as C  # noqa
from restaurante.caja_calculos import validar_montos_por_moneda, CajaInvalida

total = 0; fallos = []
def ok(n, c):
    global total; total += 1
    if not c: fallos.append(n); print('  FALLA:', n)
def regla(n, f):
    try: f()
    except C.ReglaCaja: ok(n, True)
    else: ok(n, False)

emp = types.SimpleNamespace(id=1)
ok('sin caja abierta', C.caja_abierta() is None)
regla('movimiento sin caja', lambda: C.registrar_movimiento_manual(emp, 'Ingreso', 'ARS', D('10'), 'x'))
regla('cerrar sin caja', lambda: C.cerrar_caja(emp, validar_montos_por_moneda({'ARS': 0, 'USD': 0, 'BRL': 0, 'PYG': 0}, True)))

caja = C.abrir_caja(emp, validar_montos_por_moneda({'ARS': 10000, 'USD': 50}))
ok('abre', caja.estado == 'Abierta' and C.caja_abierta() is caja)
ok('5 filas: 4 de efectivo + 1 de Mercado Pago', len(CajaMoneda.objects.items) == 5)
ok('monto_apertura ARS', caja.monto_apertura == D('10000.00'))
regla('segunda apertura', lambda: C.abrir_caja(emp, validar_montos_por_moneda(None)))

r = C.resumen_arqueo(caja)['efectivo']
ok('esperado inicial ARS', r['ARS']['esperado'] == D('10000.00') and r['USD']['esperado'] == D('50.00'))

m = C.registrar_movimiento_manual(emp, 'Ingreso', 'ARS', D('500'), 'cambio')
ok('ingreso ARS: cot 1 y monto_ars', m.cotizacion == D(1) and m.monto_ars == D('500') and m.concepto == 'Manual')
m = C.registrar_movimiento_manual(emp, 'Egreso', 'ARS', D('200'), 'proveedor')
regla('egreso mayor al saldo USD', lambda: C.registrar_movimiento_manual(emp, 'Egreso', 'USD', D('100'), 'x'))
m = C.registrar_movimiento_manual(emp, 'Ingreso', 'USD', D('10'), 'propina')
ok('ingreso USD: cotizacion y pesos', m.cotizacion == D('1500') and m.monto_ars == D('15000.00'))
m = C.registrar_movimiento_manual(emp, 'Ingreso', 'PYG', D('1000'), 'x')
ok('PYG a pesos', m.monto_ars == D('238.80'))
regla('egreso exacto mas un centavo', lambda: C.registrar_movimiento_manual(emp, 'Egreso', 'ARS', D('10300.01'), 'x'))
C.registrar_movimiento_manual(emp, 'Egreso', 'ARS', D('10300'), 'retiro total')
ok('esperado ARS en cero', C.resumen_arqueo(caja)['efectivo']['ARS']['esperado'] == D('0.00'))
C.registrar_movimiento_manual(emp, 'Ingreso', 'ARS', D('10300'), 'reingreso')
CAIDA = dict(COT); COT.pop('BRL')
regla('sin cotizacion de BRL', lambda: C.registrar_movimiento_manual(emp, 'Ingreso', 'BRL', D('5'), 'x'))
COT['BRL'] = D('280')
ok('no se creo movimiento fallido', len(MovimientoCaja.objects.items) == 6)


# ---- Mercado Pago: se anota al aprobarse el pago, no toca el cajon ----
antes = C.resumen_arqueo(caja)['efectivo']['ARS']['esperado']
m = C.registrar_movimiento(caja, 'Ingreso', 'Venta', 'ARS', D('15000'), emp, medio='MercadoPago')
ok('MP: movimiento con etiqueta', m.medio == 'MercadoPago' and m.moneda == 'ARS' and m.monto_ars == D('15000'))
m = C.registrar_movimiento(caja, 'Ingreso', 'Propina', 'ARS', D('500'), emp, medio='MercadoPago')
ok('el efectivo no cambia con Mercado Pago', C.resumen_arqueo(caja)['efectivo']['ARS']['esperado'] == antes)
rs = C.resumen_arqueo(caja)
ok('MP esperado 15500', rs['mercado_pago']['esperado'] == D('15500.00'))
ok('total en pesos = efectivo + MP', rs['total']['esperado_en_pesos']['total'] == rs['total']['esperado_en_pesos']['efectivo'] + D('15500.00'))
ok('total efectivo incluye USD convertido', rs['total']['esperado_en_pesos']['efectivo'] == D('10300.00') + D('60') * D('1500') + D('1000') * D('0.2388'))
for args, nombre in [((caja, 'Ingreso', 'Venta', 'USD', D('1'), emp), 'MP en USD'), ((caja, 'Egreso', 'Venta', 'ARS', D('1'), emp), 'MP egreso')]:
    try: C.registrar_movimiento(*args, medio='MercadoPago')
    except ValueError: ok(nombre + ' no se permite', True)
    else: ok(nombre + ' no se permite', False)
ok('manual solo efectivo (el egreso manual no toca MP)', C.registrar_movimiento_manual(emp, 'Egreso', 'ARS', D('1'), 'x').medio == 'Efectivo')

C.registrar_movimiento_manual(emp, 'Ingreso', 'ARS', D('1'), 'devuelve el peso')
r = C.resumen_arqueo(caja)['efectivo']
ok('esperado ARS final', r['ARS']['esperado'] == D('10300.00'))
ok('esperado USD final', r['USD']['esperado'] == D('60.00'))
ok('esperado PYG final', r['PYG']['esperado'] == D('1000.00'))

cuatro = validar_montos_por_moneda({'ARS': 10250, 'USD': 60, 'BRL': 0, 'PYG': 1000}, True)
try: C.cerrar_caja(emp, cuatro)
except CajaInvalida: ok('cerrar sin informar Mercado Pago (hay cobros) falla', True)
else: ok('cerrar sin informar Mercado Pago (hay cobros) falla', False)
try: C.cerrar_caja(emp, cuatro, '-5')
except CajaInvalida: ok('MP negativo falla', True)
else: ok('MP negativo falla', False)
ok('sigue abierta tras los cierres fallidos', C.caja_abierta() is caja and caja.estado == 'Abierta')
cerrada = C.cerrar_caja(emp, cuatro, '15400')
ok('cerrada', cerrada.estado == 'Cerrada' and C.caja_abierta() is None)
ok('monto_cierre ARS', cerrada.monto_cierre == D('10250.00'))
ok('totales guardados', cerrada.total_esperado_ars == D('10300.00') + D('90000') + D('238.80') + D('15500') and cerrada.total_declarado_ars == D('10250') + D('90000') + D('238.80') + D('15400'))
filas = {f.moneda: f for f in CajaMoneda.objects.items if f.medio == 'Efectivo'}
fila_mp = [f for f in CajaMoneda.objects.items if f.medio == 'MercadoPago'][0]
ok('MP: esperado, declarado y diferencia guardados', fila_mp.monto_esperado == D('15500.00') and fila_mp.monto_declarado == D('15400.00') and fila_mp.diferencia == D('-100.00'))
ok('diferencia ARS', filas['ARS'].diferencia == D('-50.00') and filas['ARS'].monto_esperado == D('10300.00'))
ok('diferencia USD 0', filas['USD'].diferencia == D('0.00'))
rc = C.resumen_arqueo(cerrada)
r = rc['efectivo']
ok('arqueo cerrado trae declarado', r['ARS']['declarado'] == D('10250.00') and r['ARS']['diferencia'] == D('-50.00'))
ok('arqueo cerrado: MP', rc['mercado_pago']['diferencia'] == D('-100.00'))
ok('arqueo cerrado: total esperado y declarado', rc['total']['esperado_en_pesos']['total'] - rc['total']['declarado_en_pesos']['total'] == D('150.00'))
regla('cerrar de nuevo', lambda: C.cerrar_caja(emp, validar_montos_por_moneda({'ARS': 0, 'USD': 0, 'BRL': 0, 'PYG': 0}, True)))
regla('movimiento con caja cerrada', lambda: C.registrar_movimiento_manual(emp, 'Ingreso', 'ARS', D('1'), 'x'))
caja2 = C.abrir_caja(emp, validar_montos_por_moneda(None))
ok('se puede abrir otra', caja2.id != caja.id and C.caja_abierta() is caja2)
ok('la nueva arranca en cero', C.resumen_arqueo(caja2)['efectivo']['ARS']['esperado'] == D('0.00'))

# bloqueo de cierre (hook del hito 3)
original = C.bloqueos_de_cierre
C.bloqueos_de_cierre = lambda c: ['Hay un cobro pendiente.']
regla('cierre bloqueado', lambda: C.cerrar_caja(emp, validar_montos_por_moneda({'ARS': 0, 'USD': 0, 'BRL': 0, 'PYG': 0}, True)))
ok('sigue abierta tras el bloqueo', C.caja_abierta() is caja2)
C.bloqueos_de_cierre = original

print(f'{total - len(fallos)}/{total} chequeos OK'); sys.exit(1 if fallos else 0)
