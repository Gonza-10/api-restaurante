"""Prueba del comprobante PDF de la factura (cobros, hito 6) sin base de datos ni la libreria de PDF: formato de importes,
nombre del archivo, validacion de la casilla "quiero factura", contenido que se arma y dibujo del PDF con un doble
ESTRICTO de fpdf2 (solo acepta los metodos y argumentos que usa el comprobante, exige texto Latin-1, que todo caiga dentro de
la hoja y que al pasar de pagina se vuelva a poner el numero de pagina).
Solo libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_comprobante_calculos.py
"""
import importlib.util
import sys
import types
from datetime import datetime
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
cc = cargar('comprobante_calculos')
pdf_mod = cargar('comprobante_pdf')

RESULTADOS = []


def chequear(nombre, obtenido, esperado):
    ok = obtenido == esperado
    RESULTADOS.append(ok)
    print(('OK   ' if ok else 'FALLA'), nombre, '' if ok else f'-> obtenido {obtenido!r}, esperado {esperado!r}')


def lanza(nombre, funcion, campo):
    try:
        funcion()
    except cc.PedidoInvalido as error:
        chequear(nombre, error.campo, campo)
    except Exception as error:
        chequear(nombre, f'{type(error).__name__}: {error}', f'PedidoInvalido({campo})')
    else:
        chequear(nombre, 'no lanzo nada', f'PedidoInvalido({campo})')


# ---------- importes con formato argentino ----------
chequear('numero_ar 1234.5', cc.numero_ar(D('1234.5')), '1.234,50')
chequear('numero_ar 0', cc.numero_ar(0), '0,00')
chequear('numero_ar negativo', cc.numero_ar(D('-1234.567')), '-1.234,57')
chequear('numero_ar sin decimales', cc.numero_ar(D('1500000'), 0), '1.500.000')
chequear('numero_ar redondea hacia arriba la mitad', cc.numero_ar(D('0.005')), '0,01')
chequear('numero_ar millones', cc.numero_ar(D('12345678.9')), '12.345.678,90')
chequear('pesos', cc.pesos(D('1500')), '$ 1.500,00')
chequear('importe USD', cc.importe(D('12.3'), 'USD'), 'USD 12,30')
chequear('importe PYG sin centavos', cc.importe(D('1500000.4'), 'PYG'), 'PYG 1.500.000')
chequear('importe None', cc.importe(None), '-')
chequear('cotizacion USD', cc.cotizacion_texto('USD', D('1200.5')), '1 USD = $ 1.200,50')
chequear('cotizacion PYG con 4 decimales', cc.cotizacion_texto('PYG', D('0.1634')), '1 PYG = $ 0,1634')
chequear('fecha_hora', cc.fecha_hora(datetime(2026, 11, 8, 19, 5)), '08/11/2026 19:05')
chequear('fecha_hora vacia', cc.fecha_hora(None), '-')
chequear('numero de factura', cc.numero_de_factura(42), 'N° 00000042')

# ---------- texto seguro para el PDF (Helvetica solo conoce Latin-1) ----------
chequear('texto_pdf None', cc.texto_pdf(None), '')
chequear('texto_pdf conserva acentos y enie', cc.texto_pdf('Café ñandú'), 'Café ñandú')
chequear('texto_pdf guion largo', cc.texto_pdf('a – b — c'), 'a - b - c')
chequear('texto_pdf comillas tipograficas', cc.texto_pdf('“hola”'), '"hola"')
chequear('texto_pdf emoji se reemplaza', cc.texto_pdf('Hola 😀'), 'Hola ?')
chequear('texto_pdf euro', cc.texto_pdf('5 €'), '5 EUR')
chequear('texto_pdf saltos de linea', cc.texto_pdf('a\nb\tc'), 'a b c')
chequear('texto_pdf largo', cc.texto_pdf('abcdefghij', 5), 'abcd.')
chequear('texto_pdf todo es Latin-1', all(ord(c) < 256 for c in cc.texto_pdf('Ω≈ç√∫ 漢字 ñ')), True)

# ---------- nombre del archivo ----------
chequear('nombre_archivo', cc.nombre_archivo('David', 5, datetime(2026, 11, 8, 19, 5)), 'David - 08-11-26.pdf')
chequear('nombre_archivo con apellido y acento', cc.nombre_archivo('José Pérez', 5, datetime(2026, 1, 2)), 'José Pérez - 02-01-26.pdf')
chequear('nombre_archivo sin nombre', cc.nombre_archivo(None, 5, datetime(2026, 11, 8)), 'Mesa 5 - 08-11-26.pdf')
chequear('nombre_archivo vacio', cc.nombre_archivo('   ', 7, datetime(2026, 11, 8)), 'Mesa 7 - 08-11-26.pdf')
chequear('nombre_guardado lleva el numero de factura', cc.nombre_guardado('David', 5, datetime(2026, 11, 8), 7), 'David - 08-11-26 (factura 7).pdf')
chequear('nombre_guardado sin nombre', cc.nombre_guardado(None, 5, datetime(2026, 11, 8), 12), 'Mesa 5 - 08-11-26 (factura 12).pdf')
chequear('nombre_guardado: dos facturas del mismo cliente no se pisan', cc.nombre_guardado('Ana', 1, datetime(2026, 11, 8), 1) != cc.nombre_guardado('Ana', 2, datetime(2026, 11, 8), 2), True)
chequear('sufijo_guardado: el archivo de la factura 7 no es el de la 77', cc.nombre_guardado('Ana', 1, datetime(2026, 11, 8), 77).endswith(cc.sufijo_guardado(7)), False)
chequear('limpiar_nombre caracteres prohibidos', cc.limpiar_nombre('Da/vid: <x>'), 'Da vid x')
chequear('limpiar_nombre barras invertidas', cc.limpiar_nombre('..\\..\\etc'), 'etc')
chequear('limpiar_nombre solo puntos', cc.limpiar_nombre('...'), '')
chequear('limpiar_nombre largo', len(cc.limpiar_nombre('a' * 200)), 80)
chequear('el nombre del archivo no tiene barras', '/' in cc.nombre_archivo('a/b', 1, datetime(2026, 11, 8)), False)

# ---------- la casilla "quiero factura" ----------
chequear('pedido: sin casilla', cc.validar_pedido_de_factura({}), None)
chequear('pedido: casilla None', cc.validar_pedido_de_factura({'quiere_factura': None}), None)
chequear('pedido: casilla vacia', cc.validar_pedido_de_factura({'quiere_factura': ''}), None)
chequear('pedido: no es un diccionario', cc.validar_pedido_de_factura(['x']), None)
chequear('pedido: false', cc.validar_pedido_de_factura({'quiere_factura': False, 'nombre_factura': 'X'}), (False, None))
chequear('pedido: "false" como texto', cc.validar_pedido_de_factura({'quiere_factura': 'false'}), (False, None))
chequear('pedido: true con nombre', cc.validar_pedido_de_factura({'quiere_factura': True, 'nombre_factura': ' David   Noguera '}), (True, 'David Noguera'))
chequear('pedido: "si"', cc.validar_pedido_de_factura({'quiere_factura': 'si', 'nombre_factura': 'Ana'}), (True, 'Ana'))
lanza('pedido: true sin nombre', lambda: cc.validar_pedido_de_factura({'quiere_factura': True}), 'nombre_factura')
lanza('pedido: true con nombre en blanco', lambda: cc.validar_pedido_de_factura({'quiere_factura': True, 'nombre_factura': '   '}), 'nombre_factura')
lanza('pedido: nombre demasiado largo', lambda: cc.validar_pedido_de_factura({'quiere_factura': True, 'nombre_factura': 'a' * 101}), 'nombre_factura')
lanza('pedido: valor que no es booleano', lambda: cc.validar_pedido_de_factura({'quiere_factura': 'quizas'}), 'quiere_factura')
chequear('pedido: nombre de 100 caracteres entra', cc.validar_pedido_de_factura({'quiere_factura': True, 'nombre_factura': 'a' * 100})[1], 'a' * 100)

# ---------- partir_texto ----------
chequear('partir: entra', cc.partir_texto('hola mundo', 20, len), ['hola mundo'])
chequear('partir: por palabras', cc.partir_texto('hola mundo cruel', 9, len), ['hola', 'mundo', 'cruel'])
chequear('partir: junta lo que entra', cc.partir_texto('aa bb cc dd', 5, len), ['aa bb', 'cc dd'])
chequear('partir: palabra mas larga que el renglon', cc.partir_texto('abcdefghij', 4, len), ['abcd', 'efgh', 'ij'])
chequear('partir: vacio', cc.partir_texto('', 10, len), [''])
chequear('partir: ninguna linea pasa del ancho', all(len(r) <= 7 for r in cc.partir_texto('Hamburguesa doble con cheddar y panceta crocante', 7, len)), True)

# ---------- el contenido ----------
pago_ars = {'fecha_hora': datetime(2026, 11, 8, 20, 30), 'medio': 'Efectivo', 'moneda': 'ARS', 'monto_recibido': D('12000'),
            'cotizacion': D('1'), 'monto': D('10000'), 'propina': D('500'), 'vuelto': D('1500')}
pago_usd = {'fecha_hora': datetime(2026, 11, 8, 20, 31), 'medio': 'Efectivo', 'moneda': 'USD', 'monto_recibido': D('10'),
            'cotizacion': D('1200'), 'monto': D('12000'), 'propina': D('0'), 'vuelto': D('0')}
pago_mp = {'fecha_hora': datetime(2026, 11, 8, 20, 32), 'medio': 'MercadoPago', 'moneda': 'ARS', 'monto_recibido': None,
           'cotizacion': D('1'), 'monto': D('8000'), 'propina': D('0'), 'vuelto': D('0')}


def datos_base(pagos, total=D('10000')):
    return {
        'id': 7, 'estado': 'Pagada', 'emision': datetime(2026, 11, 8, 20, 0), 'pago': datetime(2026, 11, 8, 20, 30), 'total': total,
        'cliente': 'David', 'mesa': 5, 'comensales': 2, 'mozo': 'Ana Gómez',
        'renglones': [
            {'cantidad': 2, 'descripcion': 'Hamburguesa doble', 'precio_unitario': D('4000'), 'sub_total': D('8000')},
            {'cantidad': 1, 'descripcion': 'Gaseosa', 'precio_unitario': D('2000'), 'sub_total': D('2000')},
        ],
        'equivalentes': {'USD': D('8.33'), 'BRL': D('40.00'), 'PYG': D('9000000')},
        'cotizaciones': {'USD': D('1200'), 'BRL': D('250'), 'PYG': D('0.0011')},
        'pagos': pagos,
    }


m = cc.armar_modelo(datos_base([pago_ars]))
chequear('modelo: titulo', m['titulo'], 'COMPROBANTE DE CONSUMO')
chequear('modelo: numero', m['numero'], 'N° 00000007')
chequear('modelo: estado en mayusculas', m['estado'], 'PAGADA')
chequear('modelo: datos generales', [e for e, _ in m['generales']], ['Cliente', 'Mesa', 'Comensales', 'Atendió', 'Emitida', 'Pagada'])
chequear('modelo: cliente', dict(m['generales'])['Cliente'], 'David')
chequear('modelo: renglones', [(r['cantidad'], r['descripcion'], r['unitario'], r['subtotal']) for r in m['renglones']],
         [('2', 'Hamburguesa doble', '$ 4.000,00', '$ 8.000,00'), ('1', 'Gaseosa', '$ 2.000,00', '$ 2.000,00')])
chequear('modelo: total', m['total'], '$ 10.000,00')
chequear('modelo: equivalentes', [(e['moneda'], e['importe'], e['cotizacion']) for e in m['equivalentes']],
         [('USD', 'USD 8,33', '1 USD = $ 1.200,00'), ('BRL', 'BRL 40,00', '1 BRL = $ 250,00'), ('PYG', 'PYG 9.000.000', '1 PYG = $ 0,0011')])
chequear('modelo: pago en pesos', m['pagos'][0],
         {'fecha': '08/11/2026 20:30', 'medio': 'Efectivo', 'recibido': '$ 12.000,00', 'cotizacion': '', 'cuenta': '$ 10.000,00',
          'propina': '$ 500,00', 'vuelto': '$ 1.500,00'})
chequear('modelo: resumen con propina y vuelto', m['resumen'],
         [('Total de la cuenta', '$ 10.000,00'), ('Propina', '$ 500,00'), ('Total cobrado', '$ 10.500,00'), ('Vuelto entregado', '$ 1.500,00')])
chequear('modelo: leyenda fiscal', m['leyendas'][0], cc.LEYENDA_FISCAL)

m2 = cc.armar_modelo(datos_base([pago_usd, pago_mp], total=D('20000')))
chequear('modelo: pago en dolares muestra lo recibido y la cotizacion', (m2['pagos'][0]['recibido'], m2['pagos'][0]['cotizacion'], m2['pagos'][0]['cuenta']),
         ('USD 10,00', '1 USD = $ 1.200,00', '$ 12.000,00'))
chequear('modelo: Mercado Pago sin monto recibido usa el de la cuenta', (m2['pagos'][1]['medio'], m2['pagos'][1]['recibido']), ('Mercado Pago', '$ 8.000,00'))
chequear('modelo: resumen sin propina ni vuelto', [e for e, _ in m2['resumen']], ['Total de la cuenta', 'Total cobrado'])
chequear('modelo: dos pagos suman lo cobrado', m2['resumen'][-1], ('Total cobrado', '$ 20.000,00'))

d3 = datos_base([pago_ars]); d3['mozo'] = None; d3['equivalentes'] = {'USD': None, 'BRL': None, 'PYG': None}
m3 = cc.armar_modelo(d3)
chequear('modelo: sin mozo no aparece "Atendió"', 'Atendió' in [e for e, _ in m3['generales']], False)
chequear('modelo: sin cotizaciones no hay equivalentes', m3['equivalentes'], [])
d4 = datos_base([pago_ars]); d4['renglones'][0]['descripcion'] = 'Menú “Salvaje” – 🍔'
chequear('modelo: la descripcion queda en Latin-1', cc.armar_modelo(d4)['renglones'][0]['descripcion'], 'Menú "Salvaje" - ?')


# ---------- el dibujo, con un doble estricto de fpdf2 ----------
class PDFEstricto:
    """Solo acepta lo que usa el comprobante, con los mismos nombres de argumento que fpdf2."""
    PAGINA = (210, 297)

    def __init__(self, orientation='P', unit='mm', format='A4'):
        assert (orientation, unit, format) == ('P', 'mm', 'A4')
        self.paginas = 0
        self.celdas, self.rects, self.lineas = [], [], []
        self.x = self.y = 0
        self.tam = 9
        self.alias = False
        self.fuente_puesta = False

    def set_auto_page_break(self, auto, margin=0): assert auto is False
    def alias_nb_pages(self, alias='{nb}'): self.alias = True
    def set_margins(self, left, top, right=-1): pass
    def set_title(self, title): assert title.encode('latin-1')
    def set_author(self, author): pass
    def add_page(self): self.paginas += 1

    def set_font(self, family, style='', size=0):
        assert family == 'Helvetica' and style in ('', 'B'), (family, style)
        self.tam, self.fuente_puesta = size or self.tam, True

    def set_text_color(self, r, g=-1, b=-1): self._color(r, g, b)
    def set_fill_color(self, r, g=-1, b=-1): self._color(r, g, b)
    def set_draw_color(self, r, g=-1, b=-1): self._color(r, g, b)
    def set_line_width(self, width): assert width > 0
    def set_xy(self, x, y): self.x, self.y = x, y

    @staticmethod
    def _color(r, g, b):
        assert all(0 <= c <= 255 for c in (r, g, b)), (r, g, b)

    def get_string_width(self, text, normalized=False, markdown=False):
        return len(text) * self.tam * 0.19

    def cell(self, w=None, h=None, text='', border=0, ln='DEPRECATED', align='', fill=False, link='', center='DEPRECATED',
             markdown=False, new_x='RIGHT', new_y='TOP'):
        assert self.fuente_puesta, 'se dibujo texto sin elegir fuente'
        assert isinstance(text, str)
        text.encode('latin-1')                         # fpdf2 con Helvetica falla con otra cosa
        assert new_x in ('RIGHT', 'LMARGIN', 'NEXT') and new_y in ('TOP', 'NEXT'), (new_x, new_y)
        self.celdas.append({'pagina': self.paginas, 'x': self.x, 'y': self.y, 'w': w, 'h': h, 'texto': text})
        self.x += w

    def rect(self, x, y, w, h, style=None, round_corners=False, corner_radius=0):
        assert style in (None, 'D', 'F', 'DF'), style
        self.rects.append({'pagina': self.paginas, 'x': x, 'y': y, 'w': w, 'h': h})

    def line(self, x1, y1, x2, y2): self.lineas.append({'pagina': self.paginas, 'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2})

    def output(self, name='', dest=''): return bytearray(b'%PDF-estricto')


def dibujar(modelo):
    doble = []

    class Molde(PDFEstricto):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            doble.append(self)

    salida = pdf_mod.dibujar(modelo, clase_pdf=Molde)
    return salida, doble[0]


def revisar(nombre, modelo):
    salida, p = dibujar(modelo)
    chequear(f'{nombre}: devuelve bytes', isinstance(salida, bytes) and salida.startswith(b'%PDF'), True)
    chequear(f'{nombre}: alias de total de paginas activado', p.alias, True)
    en_hoja = all(-0.01 <= r['x'] and r['x'] + r['w'] <= 210.01 and -0.01 <= r['y'] and r['y'] + r['h'] <= 297.01 for r in p.rects)
    chequear(f'{nombre}: los rectangulos caen dentro de la hoja', en_hoja, True)
    en_hoja = all(0 <= c['x'] and c['x'] + c['w'] <= 210.01 and 0 <= c['y'] and c['y'] + c['h'] <= 297 for c in p.celdas)
    chequear(f'{nombre}: las celdas caen dentro de la hoja', en_hoja, True)
    contenido = [c for c in p.celdas if not c['texto'].startswith('Pagina ')]
    chequear(f'{nombre}: el contenido respeta el pie', max(c['y'] + c['h'] for c in contenido) <= 297 - pdf_mod.PIE + 0.01, True)
    pies = {c['pagina'] for c in p.celdas if c['texto'].startswith('Pagina ') and c['texto'].endswith('de {nb}')}
    chequear(f'{nombre}: todas las paginas llevan su numero', pies, set(range(1, p.paginas + 1)))
    return p


chico = revisar('una pagina', cc.armar_modelo(datos_base([pago_ars])))
chequear('una pagina: es una sola', chico.paginas, 1)
textos = [c['texto'] for c in chico.celdas]
for esperado in ('COMPROBANTE DE CONSUMO', 'N° 00000007', 'Hamburguesa doble', '$ 10.500,00', 'David', 'EL TOTAL EQUIVALE A', 'USD 8,33',
                 cc.LEYENDA_FISCAL):
    chequear(f'una pagina: aparece "{esperado}"', esperado in textos or any(esperado in t for t in textos), True)
chequear('una pagina: la marca se dibuja en dos colores', ('SAVAGE ' in textos) and ('GRILL' in textos), True)

sin_pagos = datos_base([]); sin_pagos['equivalentes'] = {'USD': None, 'BRL': None, 'PYG': None}
p0 = revisar('sin pagos ni equivalentes', cc.armar_modelo(sin_pagos))
chequear('sin pagos: no hay seccion de pagos', 'PAGOS RECIBIDOS' in [c['texto'] for c in p0.celdas], False)

largo = datos_base([pago_ars, pago_usd, pago_mp] * 3, total=D('90000'))
largo['renglones'] = [{'cantidad': n % 3 + 1, 'descripcion': f'Plato numero {n} con guarnicion, salsa de la casa y extras varios para que el texto sea largo',
                       'precio_unitario': D('1500'), 'sub_total': D('1500') * (n % 3 + 1)} for n in range(70)]
p1 = revisar('muchos renglones', cc.armar_modelo(largo))
chequear('muchos renglones: pasa a mas de una pagina', p1.paginas > 1, True)
chequear('muchos renglones: se repite la cabecera de la tabla', sum(1 for c in p1.celdas if c['texto'] == 'DESCRIPCION') >= p1.paginas - 1, True)
chequear('muchos renglones: salen todos', sum(1 for c in p1.celdas if c['texto'].startswith('Plato numero')) >= 70, True)

raro = datos_base([pago_ars]); raro['cliente'] = 'Ñandú 😀 ' + 'x' * 200; raro['renglones'][0]['descripcion'] = 'p' * 300
revisar('texto raro y largo', cc.armar_modelo(raro))

total = len(RESULTADOS)
bien = sum(RESULTADOS)
print(f'\n{bien}/{total} verificaciones correctas')
sys.exit(0 if bien == total else 1)
