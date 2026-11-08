"""Prueba de la copia del comprobante en la carpeta `Facturas/` (cobros, hito 6) con dobles de la base y del PDF: se guarda cuando la
factura se pidio y esta Pagada, se reemplaza al cambiar el nombre, se borra si deja de estar Pagada o se destilda la casilla, no pisa
la factura de otro cliente con el mismo nombre, y un error de disco no se propaga (un cobro no puede fallar por esto).
Solo libreria estandar; usa una carpeta temporal.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_comprobante_dobles.py
"""
import importlib.util
import os
import sys
import tempfile
import types
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as NS

CARPETA = Path(__file__).resolve().parents[2] / 'restaurante'


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(f'restaurante.{nombre}', CARPETA / f'{nombre}.py')
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[f'restaurante.{nombre}'] = modulo
    spec.loader.exec_module(modulo)
    return modulo


class ReglaCuenta(Exception):
    def __init__(self, mensaje, estado=409, **extra):
        super().__init__(mensaje)
        self.mensaje, self.estado, self.extra = mensaje, estado, extra


class Consulta(list):
    def select_related(self, *a): return self
    def order_by(self, *a): return self
    def filter(self, **k): return self
    def get(self, pk): return next(x for x in self if x.pk == pk)


FACTURAS = Consulta()
BASE = NS(numero=5)


def nueva_factura(id_, nombre='David', estado='Pagada', pide=True, mesa=5):
    f = NS(id=id_, pk=id_, estado=estado, solicito_ticket=pide, nombre_factura=nombre if pide else None,
           fecha_hora_emision=datetime(2026, 11, 8, 20, 0), fecha_hora_pago=datetime(2026, 11, 8, 20, 30), total=D('1000'),
           total_usd=None, total_brl=None, total_pyg=None, cotizacion_usd=None, cotizacion_brl=None, cotizacion_pyg=None)
    f.pedido_cabecera = NS(mesa=NS(numero=mesa), cantidad_comensales=2, empleado=NS(nombre='Ana', apellido='Gomez'))
    FACTURAS.append(f)
    return f


paquete = types.ModuleType('restaurante'); paquete.__path__ = [str(CARPETA)]; sys.modules['restaurante'] = paquete
dj = types.ModuleType('django'); du = types.ModuleType('django.utils')
tz = types.ModuleType('django.utils.timezone'); tz.is_aware = lambda v: False; tz.localtime = lambda v: v
du.timezone = tz; dj.utils = du
sys.modules.update({'django': dj, 'django.utils': du, 'django.utils.timezone': tz})
cu = types.ModuleType('restaurante.cuenta'); cu.ReglaCuenta = ReglaCuenta; sys.modules['restaurante.cuenta'] = cu
mo = types.ModuleType('restaurante.models')
mo.Factura = NS(objects=FACTURAS)
mo.FacturaDetalle = NS(objects=Consulta([NS(cantidad=1, descripcion='Plato', precio_unitario=D('1000'), sub_total=D('1000'))]))
mo.Pago = NS(objects=Consulta([NS(fecha_hora=datetime(2026, 11, 8, 20, 30), metodo_pago=NS(nombre='Efectivo'), moneda='ARS',
                                  monto_recibido=D('1000'), cotizacion=D('1'), monto=D('1000'), monto_propina=D('0'), vuelto=D('0'))]))
sys.modules['restaurante.models'] = mo
DIBUJOS = []
pdf = types.ModuleType('restaurante.comprobante_pdf'); pdf.dibujar = lambda modelo: DIBUJOS.append(modelo) or b'%PDF-doble'
sys.modules['restaurante.comprobante_pdf'] = pdf
cargar('comprobante_calculos')
c = cargar('comprobante')

TEMP = tempfile.mkdtemp(prefix='facturas_prueba_')
c.CARPETA_FACTURAS = os.path.join(TEMP, 'Facturas')      # todavia no existe: el modulo la tiene que crear

total = 0
fallos = []


def ok(nombre, condicion):
    global total
    total += 1
    print(('OK   ' if condicion else 'FALLA'), nombre)
    if not condicion:
        fallos.append(nombre)


def archivos():
    return sorted(os.listdir(c.CARPETA_FACTURAS)) if os.path.isdir(c.CARPETA_FACTURAS) else []


f7 = nueva_factura(7)
ruta = c.sincronizar_en_facturas(7)
ok('pagada y pedida: se guarda (y crea la carpeta)', archivos() == ['David - 08-11-26 (factura 7).pdf'] and ruta == os.path.join(c.CARPETA_FACTURAS, archivos()[0]))
ok('el archivo tiene el PDF', open(ruta, 'rb').read() == b'%PDF-doble')

with open(os.path.join(c.CARPETA_FACTURAS, 'otro archivo cualquiera.pdf'), 'wb') as fh:
    fh.write(b'otro')
c.sincronizar_en_facturas(7)
ok('sincronizar dos veces no duplica y no toca otros archivos de la carpeta', archivos() == ['David - 08-11-26 (factura 7).pdf', 'otro archivo cualquiera.pdf'])

f7.nombre_factura = 'Pedro'
c.sincronizar_en_facturas(7)
ok('al cambiar el nombre se reemplaza el archivo (no queda el viejo)', archivos() == ['Pedro - 08-11-26 (factura 7).pdf', 'otro archivo cualquiera.pdf'])

f8 = nueva_factura(8, nombre='Pedro', mesa=6)
c.sincronizar_en_facturas(8)
ok('otro cliente con el mismo nombre el mismo dia no pisa al anterior', 'Pedro - 08-11-26 (factura 7).pdf' in archivos() and 'Pedro - 08-11-26 (factura 8).pdf' in archivos())
nueva_factura(77, nombre='Pedro', mesa=7)
c.sincronizar_en_facturas(77)
c.sincronizar_en_facturas(7)
ok('la factura 7 no confunde su archivo con el de la 77', 'Pedro - 08-11-26 (factura 77).pdf' in archivos() and 'Pedro - 08-11-26 (factura 7).pdf' in archivos())
os.remove(os.path.join(c.CARPETA_FACTURAS, 'Pedro - 08-11-26 (factura 77).pdf'))

f7.estado = 'Emitida'
ok('si la factura vuelve a Emitida (se anulo un pago) devuelve None', c.sincronizar_en_facturas(7) is None)
ok('...y su archivo se borra, sin tocar los demas', 'Pedro - 08-11-26 (factura 7).pdf' not in archivos() and 'Pedro - 08-11-26 (factura 8).pdf' in archivos())

f7.estado = 'Pagada'
c.sincronizar_en_facturas(7)
ok('al volver a quedar Pagada se vuelve a guardar', 'Pedro - 08-11-26 (factura 7).pdf' in archivos())
f7.solicito_ticket, f7.nombre_factura = False, None
c.sincronizar_en_facturas(7)
ok('si se destilda la casilla se borra', 'Pedro - 08-11-26 (factura 7).pdf' not in archivos())

f9 = nueva_factura(9, pide=False)
ok('Pagada pero sin pedirla: no se guarda nada', c.sincronizar_en_facturas(9) is None and not any('(factura 9)' in a for a in archivos()))
f10 = nueva_factura(10, estado='Anulada')
ok('anulada: no se guarda nada', c.sincronizar_en_facturas(10) is None and not any('(factura 10)' in a for a in archivos()))
import logging
logging.disable(logging.CRITICAL)
ok('una factura que no existe no rompe', c.sincronizar_en_facturas(999) is None)
logging.disable(logging.NOTSET)

f11 = nueva_factura(11, nombre='Ana')
real = c.dibujar
c.dibujar = lambda modelo: (_ for _ in ()).throw(RuntimeError('falla la libreria de PDF'))
logging.disable(logging.CRITICAL)
ok('si falla el PDF no se propaga el error (un cobro no se cae)', c.sincronizar_en_facturas(11) is None)
logging.disable(logging.NOTSET)
c.dibujar = real
ok('...y no queda un archivo a medias', not any('(factura 11)' in a for a in archivos()))

f12 = nueva_factura(12, nombre='Ana / "Perez": <x>')
c.sincronizar_en_facturas(12)
ok('un nombre con caracteres prohibidos en Windows se guarda limpio', 'Ana Perez x - 08-11-26 (factura 12).pdf' in archivos())

print(f'\n{total - len(fallos)}/{total} chequeos OK')
sys.exit(1 if fallos else 0)
