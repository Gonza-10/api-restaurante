"""Prueba de restaurante/cuenta.py + caja.py con dobles (sin Django ni base): modelos en memoria.
Sirve para comprobar las reglas de negocio; NO reemplaza probar contra SQL Server (bloqueos, restricciones, indices)."""
import os, sys, types, contextlib, datetime
from decimal import Decimal as D
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # raiz del repo
sys.path.insert(0, REPO)

class IntegrityError(Exception): pass
class _Tx:
    @contextlib.contextmanager
    def atomic(self): yield
dj = {n: types.ModuleType(n) for n in ['django', 'django.db', 'django.db.models', 'django.utils', 'django.utils.timezone']}
dj['django.db'].IntegrityError = IntegrityError; dj['django.db'].transaction = _Tx()
class Sum:
    def __init__(self, campo): self.campo = campo
dj['django.db.models'].Sum = Sum
dj['django.utils.timezone'].now = lambda: datetime.datetime(2026, 11, 6, 12, 0)
dj['django.utils'].timezone = dj['django.utils.timezone']; dj['django.db'].models = dj['django.db.models']
sys.modules.update(dj)

def _val(o, campo):
    if campo == 'pk': return o.id
    return getattr(o, campo)

class QS(list):
    def __init__(self, items, modelo): super().__init__(items); self.modelo = modelo
    def select_related(self, *a): return self
    def prefetch_related(self, *a): return self
    def select_for_update(self): return self
    def order_by(self, *c):
        r = QS(self, self.modelo)
        for campo in reversed(c): r.sort(key=lambda o: _val(o, campo.lstrip('-')), reverse=campo.startswith('-'))
        return r
    def first(self): return self[0] if self else None
    def exists(self): return len(self) > 0
    def count(self): return len(self)
    def exclude(self, **kw):
        malos = self.filter(**kw); return QS([o for o in self if o not in malos], self.modelo)
    def filter(self, **kw):
        res = []
        for o in self:
            ok = True
            for k, v in kw.items():
                if k.endswith('__in'): ok &= _val(o, k[:-4]) in v
                elif k.endswith('__gt'): ok &= _val(o, k[:-4]) > v
                elif hasattr(v, 'id') and not isinstance(v, (str, int)):
                    ok &= getattr(o, k + '_id', None) == v.id or getattr(o, k, None) is v
                else: ok &= _val(o, k) == v
            if ok: res.append(o)
        return QS(res, self.modelo)
    def update(self, **kw):
        for o in self:
            for k, v in kw.items(): setattr(o, k, v)
        return len(self)
    def get(self, pk=None, id=None):
        r = self.filter(pk=pk if pk is not None else id)
        if not r: raise self.modelo.DoesNotExist()
        return r[0]
    def aggregate(self, **kw):
        (alias, s), = kw.items(); return {alias: sum((getattr(o, s.campo) for o in self), D(0)) or None}
    def values(self, *c): self._vals = c; return self
    def annotate(self, **kw):
        (alias, suma), = kw.items(); g = {}
        for o in self:
            k = tuple(getattr(o, c) for c in self._vals); g[k] = g.get(k, D(0)) + getattr(o, suma.campo)
        return [dict(zip(self._vals, k), **{alias: v}) for k, v in g.items()]

class Manager:
    def __init__(self, modelo): self.modelo = modelo; self.items = []
    def __getattr__(self, n): return getattr(QS(self.items, self.modelo), n)
    def create(self, **kw):
        o = self.modelo(**kw); o.id = len(self.items) + 1; self.items.append(o); return o
    def bulk_create(self, objs):
        for o in objs: o.id = len(self.items) + 1; self.items.append(o)
    def all(self): return QS(self.items, self.modelo)

def modelo(nombre, defaults):
    class M:
        class DoesNotExist(Exception): pass
        def __init__(self, **kw):
            for k, v in defaults.items(): setattr(self, k, v)
            for k, v in kw.items():
                setattr(self, k, v)
                if hasattr(v, 'id') and not isinstance(v, (str, int)): setattr(self, k + '_id', v.id)
        def save(self, update_fields=None): pass
    M.pk = property(lambda self: self.id)
    M.__name__ = nombre; M.objects = Manager(M); return M

Caja = modelo('Caja', dict(estado='Abierta', fecha_hora_cierre=None))
CajaMoneda = modelo('CajaMoneda', dict(medio='Efectivo', monto_esperado=None, monto_declarado=None, diferencia=None, monto_apertura=D(0)))
MovimientoCaja = modelo('MovimientoCaja', dict(pago=None, descripcion=None, medio='Efectivo'))
Factura = modelo('Factura', dict(estado='Emitida', cambio_entregado=D(0), fecha_hora_pago=None))
FacturaDetalle = modelo('FacturaDetalle', {})
Pago = modelo('Pago', dict(clave_idempotencia=None, monto_propina=D(0), vuelto=D(0), empleado_propina=None, empleado=None, referencia_externa=None,
                           mp_preferencia_id=None, mp_url_pago=None, fecha_hora_expiracion=None, mp_pago_id=None, mp_estado=None, mp_monto_neto=None))
PagoEvento = modelo('PagoEvento', {})
MetodoPago = modelo('MetodoPago', {})
PedidoCabecera = modelo('PedidoCabecera', dict(estado='Abierto', cierre_forzado=False, motivo_cierre=None))
PedidoDetalle = modelo('PedidoDetalle', dict(identificador_comensal=None))
mozo = types.SimpleNamespace(id=7, nombre='Maria', apellido='Gomez')
admin = types.SimpleNamespace(id=1, nombre='Ana', apellido='Admin')
# la sesion sabe sus detalles / comandas como el ORM (related managers simulados)
class Rel:
    def __init__(self, f): self.f = f
    def __getattr__(self, n): return getattr(self.f(), n)
    def all(self): return self.f()
def _sesion_init(self):
    pass
mesa = types.SimpleNamespace(numero=5, estado=True, save=lambda update_fields=None: None)
models = types.ModuleType('restaurante.models')
for n, m in dict(Caja=Caja, CajaMoneda=CajaMoneda, MovimientoCaja=MovimientoCaja, Factura=Factura, FacturaDetalle=FacturaDetalle,
                 Pago=Pago, PagoEvento=PagoEvento, MetodoPago=MetodoPago, PedidoCabecera=PedidoCabecera, PedidoDetalle=PedidoDetalle).items():
    setattr(models, n, m)
pkg = types.ModuleType('restaurante'); pkg.__path__ = [REPO + '/restaurante']; sys.modules['restaurante'] = pkg
sys.modules['restaurante.models'] = models
COT = {'USD': D('1500'), 'BRL': D('280'), 'PYG': D('0.2388')}
cot = types.ModuleType('restaurante.cotizacion')
cot.ultima_cotizacion = lambda m: types.SimpleNamespace(valor=COT[m]) if m in COT else None
cot.cotizaciones_vigentes = lambda: dict(COT)
sys.modules['restaurante.cotizacion'] = cot
mod = types.ModuleType('restaurante.modificadores'); mod.nombres_quitados = lambda d: []
sys.modules['restaurante.modificadores'] = mod
ext = types.ModuleType('restaurante.extras'); ext.texto_extras = lambda d: list(getattr(d, 'extras_texto', []))
sys.modules['restaurante.extras'] = ext
SINCRONIZADAS = []   # hito 6: facturas cuyo comprobante se guardo o borro en Facturas/ (la carpeta real se prueba en comprobante)
comp = types.ModuleType('restaurante.comprobante'); comp.sincronizar_en_facturas = lambda factura_id: SINCRONIZADAS.append(factura_id)
sys.modules['restaurante.comprobante'] = comp
REDIS = {}
rc = types.ModuleType('restaurante.redis_client'); rc.redis_client = types.SimpleNamespace(get=lambda k: REDIS.get(k), set=lambda k, v, ex=None: REDIS.__setitem__(k, v))
sys.modules['restaurante.redis_client'] = rc
ecf = types.ModuleType('restaurante.estado_comandas'); ecf.estado_global = lambda u: REDIS.get(f'comanda:estado:{u}')
sys.modules['restaurante.estado_comandas'] = ecf

decouple = types.ModuleType('decouple'); decouple.config = lambda nombre, default=None, cast=None: default; sys.modules['decouple'] = decouple
from restaurante import caja as C, cuenta as U  # noqa
from restaurante.caja_calculos import validar_montos_por_moneda
from restaurante.cobros_calculos import CobroInvalido

total = 0; fallos = []
def ok(n, c):
    global total; total += 1
    if not c: fallos.append(n); print('  FALLA:', n)
def regla(n, f, estado=None, exc=U.ReglaCuenta):
    try: f()
    except exc as e: ok(n, estado is None or getattr(e, 'estado', 409) == estado)
    else: ok(n, False)

MetodoPago.objects.create(nombre='Efectivo'); MetodoPago.objects.create(nombre='MercadoPago')

def nueva_sesion(consumos, comandas=()):
    s = PedidoCabecera.objects.create(mesa=mesa, empleado=mozo, estado='Abierto')
    for precio, cant, com, comp in consumos:
        d = PedidoDetalle.objects.create(pedido_cabecera=s, producto=types.SimpleNamespace(nombre='Plato'), cantidad=cant,
                                         precio_unitario=D(precio), sub_total=D(precio) * cant, identificador_comensal=com)
        d.compartido = Rel(lambda comp=comp: QS([types.SimpleNamespace(participante=p) for p in comp], None))
        d.modificadores = Rel(lambda: QS([], None))
    s.detalles = Rel(lambda s=s: QS([d for d in PedidoDetalle.objects.items if d.pedido_cabecera_id == s.id], PedidoDetalle))
    s.comandas = Rel(lambda: QS([], None))
    s.mesa = mesa
    return s
# el modelo real tiene relaciones: se parchean para el doble
U.detalles_de_sesion = lambda s: list(s.detalles.all())
U.armar_cuenta = U.armar_cuenta

def comandas(sesion, estados):
    cs = []
    for i, est in enumerate(estados):
        c = types.SimpleNamespace(id_comanda_uuid=f'u{sesion.id}-{i}', estado='Aceptada'); cs.append(c); REDIS[f'comanda:estado:{c.id_comanda_uuid}'] = est
    class R:
        def filter(self, **kw): return [c for c in cs if all(getattr(c, k) == v for k, v in kw.items())]
    sesion.comandas = R()

# --- sin caja ---
s1 = nueva_sesion([('4000', 2, None, []), ('2000', 1, 'Ana', [])])   # total 10000
[d for d in PedidoDetalle.objects.items if d.pedido_cabecera_id == s1.id][0].extras_texto = ['Cheddar x2']   # hito 5
regla('emitir sin caja abierta', lambda: U.emitir_factura(s1.id, admin))
caja = C.abrir_caja(admin, validar_montos_por_moneda({'ARS': 5000, 'USD': 0, 'BRL': 0, 'PYG': 0}))
vacia = nueva_sesion([])
regla('emitir sin consumo', lambda: U.emitir_factura(vacia.id, admin))

f, creada = U.emitir_factura(s1.id, mozo)
ok('factura emitida', creada and f.estado == 'Emitida' and f.total == D('10000.00'))
ok('equivalentes congelados', f.total_usd is not None and f.cotizacion_usd == D('1500'))
ok('renglones congelados', len(FacturaDetalle.objects.items) == 2)
ok('el renglon de la factura incluye los extras', sorted(x.descripcion for x in FacturaDetalle.objects.items) == ['Plato', 'Plato (con Cheddar x2)'])
f2, creada2 = U.emitir_factura(s1.id, mozo)
ok('emitir dos veces devuelve la vigente', not creada2 and f2.id == f.id)

# --- cocina bloquea ---
comandas(s1, ['proceso'])
regla('no se cobra con comanda en proceso', lambda: U.pagar_efectivo(f.id, mozo, 'ARS', D('10000')))
comandas(s1, ['listo'])
# --- pago parcial en ARS con propina y vuelto ---
p, c = U.pagar_efectivo(f.id, mozo, 'ARS', D('6000'), propina_ars=D('500'), monto_cuenta=D('5000'), clave='k1')
ok('pago parcial aprobado', c and p.estado == 'Aprobado' and p.monto == D('5000.00') and p.monto_propina == D('500.00') and p.vuelto == D('500.00'))
ok('propina al mozo de la mesa', p.empleado_propina is mozo)
ok('factura sigue Emitida', f.estado == 'Emitida')
p_re, c_re = U.pagar_efectivo(f.id, mozo, 'ARS', D('6000'), propina_ars=D('500'), monto_cuenta=D('5000'), clave='k1')
ok('idempotencia: mismo pago, no se cobra dos veces', not c_re and p_re.id == p.id and len(Pago.objects.items) == 1)
ok('saldo 5000', U.saldo_de_factura(f) == D('5000.00'))
esp = C.resumen_arqueo(caja)['efectivo']['ARS']['esperado']
ok('caja: 5000 apertura + 5500 venta + 500 propina - 500 vuelto', esp == D('10500.00'))
regla('monto mayor al saldo', lambda: U.pagar_efectivo(f.id, mozo, 'ARS', D('9000'), monto_cuenta=D('5000.01')), exc=CobroInvalido)

# --- pago en USD: 3 USD = 4500 ARS, no alcanza; luego 4 USD = 6000 -> cubre 5000 y 1000 de vuelto ---
regla('USD no alcanza', lambda: U.pagar_efectivo(f.id, mozo, 'USD', D('1'), monto_cuenta=D('5000')), exc=CobroInvalido)
p2, _ = U.pagar_efectivo(f.id, mozo, 'USD', D('4'))
ok('pago USD: aplica saldo, vuelto en ARS', p2.monto == D('5000.00') and p2.vuelto == D('1000.00') and p2.cotizacion == D('1500'))
ok('factura Pagada', f.estado == 'Pagada' and f.fecha_hora_pago is not None)
ok('al quedar Pagada se sincroniza el comprobante de Facturas/', SINCRONIZADAS.count(f.id) == 1)
usd = C.resumen_arqueo(caja)['efectivo']['USD']['esperado']
ok('caja: entraron 4 USD', usd == D('4.00'))
ok('vuelto acumulado en la factura', f.cambio_entregado == D('1500.00'))
ok('sobremesa: sesion abierta con factura Pagada', U.factura_vigente(s1).estado == 'Pagada')

# --- anulaciones ---
regla('anular sin motivo', lambda: U.anular_pago(p2.id, admin, '  '), estado=400)
regla('anular factura con pagos', lambda: U.anular_factura(f.id, admin, 'x'))
a = U.anular_pago(p2.id, admin, 'error de carga')
ok('pago anulado y factura vuelve a Emitida', a.estado == 'Anulado' and f.estado == 'Emitida' and U.saldo_de_factura(f) == D('5000.00'))
ok('al volver a Emitida se sincroniza otra vez (borra el archivo)', SINCRONIZADAS.count(f.id) == 2)
ok('caja: USD devuelto a cero', C.resumen_arqueo(caja)['efectivo']['USD']['esperado'] == D('0.00'))
ok('caja ARS tras anular (vuelto recuperado)', C.resumen_arqueo(caja)['efectivo']['ARS']['esperado'] == D('10500.00'))
regla('no se anula dos veces', lambda: U.anular_pago(p2.id, admin, 'x'))

# --- cierre de mesa ---
# un pedido listo pero sin entregar impide cerrar la mesa; solo Admin/Gerente fuerzan (con motivo)
regla('cerrar con un pedido listo sin entregar: 409', lambda: U.cerrar_sesion(s1.id, mozo, False))
regla('el mozo no fuerza el cierre con pedidos sin entregar', lambda: U.cerrar_sesion(s1.id, mozo, False, forzar=True, motivo='x'), estado=403)
regla('forzar sin motivo con pedidos sin entregar', lambda: U.cerrar_sesion(s1.id, admin, True, forzar=True), estado=400)
REDIS.pop(f'comanda:estado:u{s1.id}-0')   # la cocina entrega el pedido
regla('cerrar con saldo: 409', lambda: U.cerrar_sesion(s1.id, mozo, False))
regla('mozo no fuerza', lambda: U.cerrar_sesion(s1.id, mozo, False, forzar=True, motivo='x'), estado=403)
regla('forzar sin motivo', lambda: U.cerrar_sesion(s1.id, admin, True, forzar=True), estado=400)
U.pagar_efectivo(f.id, mozo, 'ARS', D('5000'))
ok('factura Pagada de nuevo', f.estado == 'Pagada')
cerrada = U.cerrar_sesion(s1.id, mozo, False)
ok('cierra con factura pagada', cerrada.estado == 'Cerrado' and not cerrada.cierre_forzado and mesa.estado is False)
regla('cerrar dos veces', lambda: U.cerrar_sesion(s1.id, mozo, False))

mesa.estado = True
sv = nueva_sesion([])
ok('mesa sin consumo se cierra sola', U.cerrar_sesion(sv.id, mozo, False).estado == 'Cerrado')

mesa.estado = True
s3 = nueva_sesion([('3000', 1, None, [])])
f3, _ = U.emitir_factura(s3.id, mozo)
cf = U.cerrar_sesion(s3.id, admin, True, forzar=True, motivo='se fueron sin pagar')
ok('cierre forzado: registra motivo y anula factura', cf.cierre_forzado and cf.motivo_cierre == 'se fueron sin pagar' and f3.estado == 'Anulada')

# --- anular factura sin pagos ---
mesa.estado = True
s4 = nueva_sesion([('3000', 1, None, [])])
f4, _ = U.emitir_factura(s4.id, mozo)
U.anular_factura(f4.id, admin, 'error')
ok('factura anulada, se puede emitir otra', f4.estado == 'Anulada' and U.emitir_factura(s4.id, mozo)[1])

# --- cierre con pago pendiente ---
f5 = U.factura_vigente(s4)
Pago.objects.create(factura=f5, estado='Pendiente', monto=D('1000'), metodo_pago=MetodoPago.objects.items[1])
regla('pago pendiente impide cerrar mesa', lambda: U.cerrar_sesion(s4.id, admin, True, forzar=True, motivo='x'))
ok('pago pendiente impide cerrar caja', len(C.bloqueos_de_cierre(caja)) == 1)
regla('factura con pago pendiente no se anula', lambda: U.anular_factura(f5.id, admin, 'x'))

# --- cuenta ---
cu = U.armar_cuenta(s4)
ok('cuenta: saldo descuenta el pendiente', cu['saldo'] == D('2000.00') and cu['puede_cobrarse'] and not cu['en_sobremesa'])


# =====================================================================================
# Hito 4: Mercado Pago (pagos_mp.py con la pasarela simulada y Redis en memoria)
# =====================================================================================
import json
from datetime import timedelta
from restaurante import pagos_mp as MP, mercadopago as M

gw = M.PasarelaSimulada(types.SimpleNamespace(get=lambda k: REDIS.get(k), set=lambda k, v, ex=None: REDIS.__setitem__(k, v)))
AHORA = datetime.datetime(2026, 11, 6, 12, 0)
mov = lambda **kw: [m for m in MovimientoCaja.objects.items if all(getattr(m, k) == v for k, v in kw.items())]
efectivo_ars = lambda: C.resumen_arqueo(caja)['efectivo']['ARS']['esperado']

# --- sesion con 10000 de consumo
mesa.estado = True
s6 = nueva_sesion([('5000', 2, None, [])])
comandas(s6, ['proceso'])
regla('MP: no se inicia con pedidos en preparacion', lambda: MP.iniciar_pago(s6, None, D(0), None, gw))
ok('MP: con pedidos en cocina no se emite la factura', U.factura_vigente(s6) is None)
comandas(s6, ['listo'])
regla('MP: monto mayor al total (sin factura)', lambda: MP.iniciar_pago(s6, D('10000.01'), D(0), None, gw), exc=CobroInvalido)
ok('MP: un monto invalido tampoco emite la factura', U.factura_vigente(s6) is None)
regla('MP: monto mayor al saldo', lambda: MP.iniciar_pago(s6, D('10000.01'), D(0), None, gw), exc=CobroInvalido)
regla('MP: propina negativa', lambda: MP.iniciar_pago(s6, D('1000'), D('-1'), None, gw), exc=CobroInvalido)
regla('MP: monto cero', lambda: MP.iniciar_pago(s6, D('0'), D(0), None, gw), exc=CobroInvalido)

m1, c1 = MP.iniciar_pago(s6, D('4000'), D('400'), 'mp1', gw)
f6 = U.factura_vigente(s6)
ok('MP: factura emitida al iniciar (sin empleado)', f6 is not None and f6.estado == 'Emitida' and f6.empleado is None)
ok('MP: pago pendiente por cuenta + propina', c1 and m1.estado == 'Pendiente' and m1.monto == D('4000') and m1.monto_recibido == D('4400') and m1.moneda == 'ARS')
ok('MP: referencia y link', m1.referencia_externa == f'SG-{m1.id}' and m1.mp_url_pago and m1.mp_preferencia_id and m1.fecha_hora_expiracion > AHORA)
ok('MP: propina al mozo de la mesa, sin empleado cajero', m1.empleado_propina is mozo and m1.empleado is None)
m1b, c1b = MP.iniciar_pago(s6, D('4000'), D('400'), 'mp1', gw)
m1c, c1c = MP.iniciar_pago(s6, None, D(0), None, gw)
ok('MP: reintento con la misma clave o sin clave devuelve el mismo pago', not c1b and not c1c and m1b.id == m1.id and m1c.id == m1.id)
ok('MP: el pendiente reserva su monto (saldo 6000)', U.saldo_de_factura(f6) == D('6000.00'))
ok('MP: pendiente bloquea el cierre de caja', len(C.bloqueos_de_cierre(caja)) == 1)
regla('MP: cerrar la mesa con pago pendiente', lambda: U.cerrar_sesion(s6.id, admin, True, forzar=True, motivo='x'))
regla('MP: factura con pago pendiente no se anula', lambda: U.anular_factura(f6.id, admin, 'x'))
regla('MP: efectivo no puede pasarse del saldo libre', lambda: U.pagar_efectivo(f6.id, mozo, 'ARS', D('7000'), monto_cuenta=D('6000.01')), exc=CobroInvalido)

# --- sin pagos todavia: sigue pendiente
r = MP.sincronizar_pago(m1.id, gw, ahora=AHORA)
ok('MP: sin pagos sigue Pendiente', r.estado == 'Pendiente' and not mov(medio='MercadoPago'))
# --- el cliente intenta y lo rechazan: el cobro sigue abierto
gw.simular(m1.referencia_externa, 'rejected', D('4400'))
r = MP.sincronizar_pago(m1.id, gw, ahora=AHORA)
ok('MP: un rechazo no termina el cobro', r.estado == 'Pendiente' and r.mp_estado == 'rejected')
n_eventos = len(PagoEvento.objects.items)
MP.sincronizar_pago(m1.id, gw, ahora=AHORA)
ok('MP: el mismo estado no repite eventos', len(PagoEvento.objects.items) == n_eventos)
# --- combinable con efectivo mientras esta pendiente
pe, _ = U.pagar_efectivo(f6.id, mozo, 'ARS', D('5000'))
ok('MP: efectivo mientras hay un MP pendiente', pe.monto == D('5000.00') and U.saldo_de_factura(f6) == D('1000.00'))
# --- pago en proceso: no vence ni se cancela
gw.simular(m1.referencia_externa, 'in_process', D('4400'))
r = MP.sincronizar_pago(m1.id, gw, ahora=m1.fecha_hora_expiracion + timedelta(hours=1))
ok('MP: en proceso no vence aunque pase el tiempo', r.estado == 'Pendiente')
regla('MP: no se cancela con un pago en proceso', lambda: MP.cancelar_pago(m1.id, admin, 'x', gw))
# --- aprobado
ef_antes = efectivo_ars()
gw.simular(m1.referencia_externa, 'approved', D('4400'))
r = MP.sincronizar_pago(m1.id, gw, ahora=AHORA)
ok('MP: aprobado', r.estado == 'Aprobado' and r.mp_pago_id and r.mp_monto_neto == D('3960.00') and r.mp_estado == 'approved')
ventas = mov(pago=m1, concepto='Venta'); props = mov(pago=m1, concepto='Propina')
ok('MP: caja anota Venta y Propina con medio MercadoPago, sin empleado', len(ventas) == 1 and len(props) == 1
   and ventas[0].medio == 'MercadoPago' and ventas[0].monto == D('4000') and props[0].monto == D('400') and ventas[0].empleado is None)
arq = C.resumen_arqueo(caja)
ok('MP: arqueo MercadoPago esperado 4400 y el efectivo no cambia', arq['mercado_pago']['esperado'] == D('4400.00') and efectivo_ars() == ef_antes)
ok('MP: factura sigue Emitida (falta 1000)', f6.estado == 'Emitida' and U.saldo_de_factura(f6) == D('1000.00'))
MP.sincronizar_pago(m1.id, gw, ahora=AHORA); MP.sincronizar_pago(m1.id, gw, ahora=AHORA)
ok('MP: sincronizar de nuevo no duplica movimientos', len(mov(pago=m1)) == 2)
regla('MP: anular pago de Mercado Pago', lambda: U.anular_pago(m1.id, admin, 'x'))
U.pagar_efectivo(f6.id, mozo, 'ARS', D('1000'))
ok('MP: factura Pagada al completar con efectivo', f6.estado == 'Pagada')
regla('MP: cuenta cubierta, no se inicia otro cobro', lambda: MP.iniciar_pago(s6, None, D(0), None, gw))

# --- monto distinto: no se aprueba solo
mesa.estado = True
s7 = nueva_sesion([('3000', 1, None, [])])
m7, _ = MP.iniciar_pago(s7, None, D('300'), None, gw)
ok('MP: sin monto paga todo el saldo', m7.monto == D('3000') and m7.monto_recibido == D('3300'))
gw.simular(m7.referencia_externa, 'approved', D('3500'))
r = MP.sincronizar_pago(m7.id, gw, ahora=AHORA)
ok('MP: monto distinto no aprueba y deja evento', r.estado == 'Pendiente' and r.mp_estado == 'monto-distinto'
   and any(e.evento == 'Monto distinto' for e in PagoEvento.objects.items if e.pago is m7) and not mov(pago=m7))
regla('MP: con aprobado de otro monto no se cancela', lambda: MP.cancelar_pago(m7.id, admin, 'x', gw))
r = MP.sincronizar_pago(m7.id, gw, ahora=m7.fecha_hora_expiracion + timedelta(hours=1))
ok('MP: monto distinto tampoco vence solo', r.estado == 'Pendiente')

# --- vencimiento
mesa.estado = True
s8 = nueva_sesion([('2000', 1, None, [])])
m8, _ = MP.iniciar_pago(s8, None, D(0), None, gw)
r = MP.sincronizar_pago(m8.id, gw, ahora=m8.fecha_hora_expiracion + timedelta(seconds=30))
ok('MP: recien vencido espera el margen', r.estado == 'Pendiente')
r = MP.sincronizar_pago(m8.id, gw, ahora=m8.fecha_hora_expiracion + timedelta(minutes=3))
ok('MP: vencido sin pagos -> Expirado y libera el saldo', r.estado == 'Expirado' and U.saldo_de_factura(U.factura_vigente(s8)) == D('2000.00'))
nuevo8, creado8 = MP.iniciar_pago(s8, None, D(0), None, gw)
ok('MP: despues de expirar se puede iniciar otro', creado8 and nuevo8.id != m8.id)
# --- aprobacion tardia sobre el pago expirado
gw.simular(m8.referencia_externa, 'approved', D('2000'))
r = MP.sincronizar_pago(m8.id, gw, ahora=m8.fecha_hora_expiracion + timedelta(minutes=10))
ok('MP: aprobacion tardia se registra', r.estado == 'Aprobado' and len(mov(pago=m8, concepto='Venta')) == 1
   and any(e.evento == 'Aprobacion tardia' for e in PagoEvento.objects.items if e.pago is m8))
ok('MP: con tardio aprobado el segundo pendiente sigue y la cuenta ya esta cubierta', U.factura_vigente(s8).estado == 'Pagada')
r = MP.sincronizar_pago(nuevo8.id, gw, ahora=nuevo8.fecha_hora_expiracion + timedelta(minutes=3))
ok('MP: el segundo, sin pagos, vence', r.estado == 'Expirado')
# fuera de la ventana de aprobacion tardia ya no se mira
r = MP.sincronizar_pago(m8.id, gw, ahora=m8.fecha_hora_expiracion + timedelta(days=2))
ok('MP: pago ya aprobado no cambia', r.estado == 'Aprobado')

# --- cancelar
mesa.estado = True
s9 = nueva_sesion([('2500', 1, None, [])])
m9, _ = MP.iniciar_pago(s9, D('1000'), D('0'), None, gw)
r = MP.cancelar_pago(m9.id, None, 'Cancelado por el cliente', gw)
ok('MP: cancelado libera el saldo', r.estado == 'Cancelado' and U.saldo_de_factura(U.factura_vigente(s9)) == D('2500.00'))
ok('MP: cancelar de nuevo no hace nada', MP.cancelar_pago(m9.id, None, 'x', gw).estado == 'Cancelado')
m9b, _ = MP.iniciar_pago(s9, None, D(0), None, gw)
gw.simular(m9b.referencia_externa, 'approved', D('2500'))
regla('MP: no se cancela uno ya pagado', lambda: MP.cancelar_pago(m9b.id, admin, 'x', gw))
ok('MP: el cancelar de uno ya pagado lo deja Aprobado', Pago.objects.get(pk=m9b.id).estado == 'Aprobado')

# --- pasarela que falla al crear el link
class Caida:
    def crear_preferencia(self, *a, **k): raise M.MercadoPagoError('sin red')
mesa.estado = True
s10 = nueva_sesion([('1500', 1, None, [])])
regla('MP: si Mercado Pago no responde -> 502 y el pago queda Cancelado', lambda: MP.iniciar_pago(s10, None, D(0), None, Caida()), estado=502)
pc = [p for p in Pago.objects.items if p.factura_id == U.factura_vigente(s10).id]
ok('MP: el pago fallido no reserva saldo', len(pc) == 1 and pc[0].estado == 'Cancelado' and U.saldo_de_factura(U.factura_vigente(s10)) == D('1500.00'))

# --- sin caja abierta no se aprueba (queda Pendiente para reintentar)
mesa.estado = True
s11 = nueva_sesion([('1200', 1, None, [])])
m11, _ = MP.iniciar_pago(s11, None, D(0), None, gw)
gw.simular(m11.referencia_externa, 'approved', D('1200'))
real = MP.caja_abierta_bloqueada; MP.caja_abierta_bloqueada = lambda: None
regla('MP: aprobado sin caja abierta -> no registra', lambda: MP.sincronizar_pago(m11.id, gw, ahora=AHORA))
MP.caja_abierta_bloqueada = real
ok('MP: sin caja queda Pendiente y sin movimientos', Pago.objects.get(pk=m11.id).estado == 'Pendiente' and not mov(pago=m11))
ok('MP: con caja de nuevo se aprueba', MP.sincronizar_pago(m11.id, gw, ahora=AHORA).estado == 'Aprobado' and len(mov(pago=m11)) == 1)
# --- funciones puras
ok('MP: normalizar_pago', M.normalizar_pago({'id': 99, 'status': 'approved', 'status_detail': 'accredited', 'transaction_amount': 4400.0,
   'transaction_details': {'net_received_amount': 4202.4}}) == {'id': '99', 'estado': 'approved', 'detalle': 'accredited', 'monto': D('4400.0'), 'neto': D('4202.4')})
ok('MP: resolver_estado prioridades', M.resolver_estado([])[0] == 'sin_pagos'
   and M.resolver_estado([{'estado': 'rejected'}])[0] == 'rechazado'
   and M.resolver_estado([{'estado': 'rejected'}, {'estado': 'in_process'}])[0] == 'en_curso'
   and M.resolver_estado([{'estado': 'in_process'}, {'estado': 'approved'}])[0] == 'aprobado')

print(f'\n{total - len(fallos)}/{total} chequeos OK')
sys.exit(1 if fallos else 0)
