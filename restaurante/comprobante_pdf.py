"""Dibuja el comprobante PDF de la factura (cobros, hito 6) a partir del contenido que arma `comprobante_calculos.armar_modelo`.

Usa solo lo basico de fpdf2 (celdas, rectangulos, lineas) y calcula a mano los saltos de renglon y de pagina, asi el resultado
no depende de funciones que cambian entre versiones. Paleta de la marca: negro, naranja #ff7a00 y grises."""
from .comprobante_calculos import partir_texto

ANCHO, ALTO = 210, 297
MARGEN = 12
UTIL = ANCHO - 2 * MARGEN            # 186 mm
PIE = 22                             # alto reservado abajo para el numero de pagina
NEGRO, NARANJA, GRIS, GRIS_CLARO, BLANCO, TEXTO = (17, 17, 17), (255, 122, 0), (110, 110, 110), (244, 244, 249), (255, 255, 255), (26, 26, 26)

# columnas (mm): renglones y pagos. Cada lista suma UTIL.
COL_RENGLONES = (16, 98, 36, 36)
COL_PAGOS = (30, 26, 44, 30, 28, 28)


class _Pagina:
    """Lleva el cursor vertical y arma una pagina nueva (con el encabezado chico) cuando no entra lo que sigue."""

    def __init__(self, pdf, modelo):
        self.pdf, self.modelo = pdf, modelo
        self.y = 0
        self.numero = 0

    def nueva(self, primera=False):
        pdf = self.pdf
        pdf.add_page()
        self.numero += 1
        _texto(pdf, MARGEN, ALTO - 12, UTIL, 4, f'Pagina {self.numero} de {{nb}}', tam=7, color=GRIS, alinear='C')   # {nb}: total de paginas (alias de fpdf2)
        if primera:
            _encabezado_grande(pdf, self.modelo)
            self.y = 52
        else:
            _encabezado_chico(pdf, self.modelo)
            self.y = 26

    def asegurar(self, alto, repetir=None):
        """Si `alto` no entra en lo que queda de la pagina, pasa a otra. `repetir` redibuja el encabezado de una tabla."""
        if self.y + alto > ALTO - PIE:
            self.nueva()
            if repetir:
                repetir()
            return True
        return False


def _texto(pdf, x, y, ancho, alto, texto, tam=9, estilo='', color=TEXTO, alinear='L', fondo=None):
    pdf.set_font('Helvetica', estilo, tam)
    pdf.set_text_color(*color)
    if fondo is not None:
        pdf.set_fill_color(*fondo)
    pdf.set_xy(x, y)
    pdf.cell(ancho, alto, texto, align=alinear, fill=fondo is not None, new_x='RIGHT', new_y='TOP')


def _marca(pdf, x, y, tam):
    pdf.set_font('Helvetica', 'B', tam)
    pdf.set_text_color(*BLANCO)
    ancho = pdf.get_string_width('SAVAGE ')
    pdf.set_xy(x, y)
    pdf.cell(ancho, tam * 0.45, 'SAVAGE ', new_x='RIGHT', new_y='TOP')
    pdf.set_text_color(*NARANJA)
    pdf.cell(pdf.get_string_width('GRILL'), tam * 0.45, 'GRILL', new_x='RIGHT', new_y='TOP')


def _encabezado_grande(pdf, modelo):
    pdf.set_fill_color(*NEGRO)
    pdf.rect(0, 0, ANCHO, 38, style='F')
    pdf.set_fill_color(*NARANJA)
    pdf.rect(0, 38, ANCHO, 1.6, style='F')
    _marca(pdf, MARGEN, 13, 24)
    _texto(pdf, ANCHO - MARGEN - 80, 11, 80, 6, modelo['titulo'], tam=11, estilo='B', color=BLANCO, alinear='R')
    _texto(pdf, ANCHO - MARGEN - 80, 18, 80, 6, modelo['numero'], tam=12, estilo='B', color=NARANJA, alinear='R')
    _texto(pdf, ANCHO - MARGEN - 80, 26, 80, 5, 'Estado: ' + modelo['estado'], tam=8, color=(190, 190, 190), alinear='R')


def _encabezado_chico(pdf, modelo):
    pdf.set_fill_color(*NEGRO)
    pdf.rect(0, 0, ANCHO, 16, style='F')
    pdf.set_fill_color(*NARANJA)
    pdf.rect(0, 16, ANCHO, 1, style='F')
    _marca(pdf, MARGEN, 5.5, 13)
    _texto(pdf, ANCHO - MARGEN - 80, 5.5, 80, 6, f"{modelo['titulo']}  {modelo['numero']}", tam=8, estilo='B', color=BLANCO, alinear='R')


def _datos_generales(pagina):
    """Dos columnas de 'ETIQUETA / valor'."""
    pdf, filas = pagina.pdf, pagina.modelo['generales']
    mitad = (len(filas) + 1) // 2
    columnas = (filas[:mitad], filas[mitad:])
    alto_fila = 9
    pagina.asegurar(alto_fila * mitad + 4)
    ancho_col = UTIL / 2
    for indice, columna in enumerate(columnas):
        x = MARGEN + indice * ancho_col
        for n, (etiqueta, valor) in enumerate(columna):
            y = pagina.y + n * alto_fila
            _texto(pdf, x, y, ancho_col - 4, 4, etiqueta.upper(), tam=6.5, estilo='B', color=GRIS)
            _texto(pdf, x, y + 3.6, ancho_col - 4, 5, valor, tam=10, estilo='B')
    pagina.y += alto_fila * mitad + 4


def _titulo_seccion(pagina, texto):
    pagina.asegurar(14)
    pdf = pagina.pdf
    pdf.set_fill_color(*NARANJA)
    pdf.rect(MARGEN, pagina.y + 0.5, 1.4, 5, style='F')
    _texto(pdf, MARGEN + 3.5, pagina.y, UTIL - 3.5, 6, texto.upper(), tam=9, estilo='B')
    pagina.y += 8.5


def _cabecera_tabla(pagina, columnas, titulos, alineaciones):
    pdf = pagina.pdf
    pdf.set_fill_color(*NEGRO)
    pdf.rect(MARGEN, pagina.y, UTIL, 7, style='F')
    x = MARGEN
    for ancho, titulo, alinear in zip(columnas, titulos, alineaciones):
        _texto(pdf, x + 1.5, pagina.y + 1, ancho - 3, 5, titulo, tam=7.5, estilo='B', color=BLANCO, alinear=alinear)
        x += ancho
    pagina.y += 7


def _renglones(pagina):
    pdf, modelo = pagina.pdf, pagina.modelo
    titulos, alin = ('CANT.', 'DESCRIPCION', 'P. UNITARIO', 'SUBTOTAL'), ('C', 'L', 'R', 'R')
    _titulo_seccion(pagina, 'Detalle del consumo')
    pagina.asegurar(7 + 8)
    _cabecera_tabla(pagina, COL_RENGLONES, titulos, alin)
    pdf.set_font('Helvetica', '', 9)
    medir = pdf.get_string_width
    ancho_desc = COL_RENGLONES[1] - 3
    for n, fila in enumerate(modelo['renglones']):
        lineas = partir_texto(fila['descripcion'], ancho_desc, medir)
        alto = 5 * len(lineas) + 2.5
        pagina.asegurar(alto, repetir=lambda: _cabecera_tabla(pagina, COL_RENGLONES, titulos, alin))
        if n % 2 == 0:
            pdf.set_fill_color(*GRIS_CLARO)
            pdf.rect(MARGEN, pagina.y, UTIL, alto, style='F')
        x = MARGEN
        _texto(pdf, x + 1.5, pagina.y + 1.2, COL_RENGLONES[0] - 3, 5, fila['cantidad'], alinear='C')
        x += COL_RENGLONES[0]
        for k, linea in enumerate(lineas):
            _texto(pdf, x + 1.5, pagina.y + 1.2 + 5 * k, ancho_desc, 5, linea)
        x += COL_RENGLONES[1]
        _texto(pdf, x + 1.5, pagina.y + 1.2, COL_RENGLONES[2] - 3, 5, fila['unitario'], alinear='R')
        x += COL_RENGLONES[2]
        _texto(pdf, x + 1.5, pagina.y + 1.2, COL_RENGLONES[3] - 3, 5, fila['subtotal'], estilo='B', alinear='R')
        pagina.y += alto
    pdf.set_draw_color(*NEGRO)
    pdf.set_line_width(0.4)
    pdf.line(MARGEN, pagina.y, MARGEN + UTIL, pagina.y)
    pagina.y += 3


def _totales(pagina):
    """Cuadro de la derecha con el total y, a la izquierda, lo que equivale en otras monedas."""
    pdf, modelo = pagina.pdf, pagina.modelo
    equivalentes = modelo['equivalentes']
    alto = max(16, 7 + 6 * len(equivalentes))
    pagina.asegurar(alto + 4)
    y = pagina.y
    if equivalentes:
        _texto(pdf, MARGEN, y, 90, 4, 'EL TOTAL EQUIVALE A', tam=6.5, estilo='B', color=GRIS)
        for n, eq in enumerate(equivalentes):
            _texto(pdf, MARGEN, y + 5 + 6 * n, 36, 5, eq['importe'], tam=10, estilo='B')
            _texto(pdf, MARGEN + 38, y + 5.6 + 6 * n, 60, 4, eq['cotizacion'], tam=7.5, color=GRIS)
    x0, ancho = MARGEN + UTIL - 78, 78
    pdf.set_fill_color(*NEGRO)
    pdf.rect(x0, y, ancho, 15, style='F')
    _texto(pdf, x0 + 4, y + 2.5, 30, 4, 'TOTAL', tam=7, estilo='B', color=(190, 190, 190))
    _texto(pdf, x0 + 4, y + 7, ancho - 8, 7, modelo['total'], tam=15, estilo='B', color=NARANJA, alinear='R')
    pagina.y += max(alto, 15) + 5


def _pagos(pagina):
    pdf, modelo = pagina.pdf, pagina.modelo
    titulos = ('FECHA Y HORA', 'MEDIO', 'RECIBIDO', 'A LA CUENTA', 'PROPINA', 'VUELTO')
    alin = ('L', 'L', 'L', 'R', 'R', 'R')
    _titulo_seccion(pagina, 'Pagos recibidos')
    pagina.asegurar(7 + 10)
    _cabecera_tabla(pagina, COL_PAGOS, titulos, alin)
    for n, fila in enumerate(modelo['pagos']):
        alto = 10.5 if fila['cotizacion'] else 7.5
        pagina.asegurar(alto, repetir=lambda: _cabecera_tabla(pagina, COL_PAGOS, titulos, alin))
        if n % 2 == 0:
            pdf.set_fill_color(*GRIS_CLARO)
            pdf.rect(MARGEN, pagina.y, UTIL, alto, style='F')
        x = MARGEN
        valores = (fila['fecha'], fila['medio'], fila['recibido'], fila['cuenta'], fila['propina'], fila['vuelto'])
        for ancho, valor, alinear in zip(COL_PAGOS, valores, alin):
            _texto(pdf, x + 1.5, pagina.y + 1.2, ancho - 3, 5, valor, tam=8.5, alinear=alinear)
            x += ancho
        if fila['cotizacion']:
            _texto(pdf, MARGEN + COL_PAGOS[0] + COL_PAGOS[1] + 1.5, pagina.y + 5.6, COL_PAGOS[2] - 3, 4, fila['cotizacion'], tam=6.5, color=GRIS)
        pagina.y += alto
    pagina.y += 3


def _resumen(pagina):
    pdf, filas = pagina.pdf, pagina.modelo['resumen']
    pagina.asegurar(7 * len(filas) + 6)
    x0, ancho = MARGEN + UTIL - 90, 90
    for n, (etiqueta, valor) in enumerate(filas):
        ultimo = n == len(filas) - 1 and len(filas) > 1 and etiqueta == 'Total cobrado'
        estilo = 'B' if ultimo or n == 0 else ''
        _texto(pdf, x0, pagina.y, 50, 6, etiqueta, tam=9, estilo=estilo, color=TEXTO if estilo else GRIS)
        _texto(pdf, x0 + 50, pagina.y, 40, 6, valor, tam=9.5, estilo=estilo, alinear='R')
        pagina.y += 6
        if ultimo:
            pdf.set_draw_color(*NARANJA)
            pdf.set_line_width(0.5)
            pdf.line(x0, pagina.y - 6.2, x0 + ancho, pagina.y - 6.2)
    pagina.y += 5


def _leyendas(pagina):
    pdf = pagina.pdf
    pagina.asegurar(16)
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.2)
    pdf.line(MARGEN, pagina.y, MARGEN + UTIL, pagina.y)
    pagina.y += 3
    for n, leyenda in enumerate(pagina.modelo['leyendas']):
        _texto(pdf, MARGEN, pagina.y, UTIL, 5, leyenda, tam=7.5 if n == 0 else 9, estilo='' if n == 0 else 'B',
               color=GRIS if n == 0 else TEXTO, alinear='C')
        pagina.y += 5 if n == 0 else 6


def dibujar(modelo, clase_pdf=None):
    """Devuelve los bytes del PDF. `clase_pdf` permite probar con un doble en lugar de fpdf2."""
    if clase_pdf is None:
        from fpdf import FPDF as clase_pdf
    pdf = clase_pdf(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.alias_nb_pages()
    pdf.set_margins(MARGEN, MARGEN, MARGEN)
    pdf.set_title(f"{modelo['titulo']} {modelo['numero']}")
    pdf.set_author('Savage Grill')
    pagina = _Pagina(pdf, modelo)
    pagina.nueva(primera=True)
    _datos_generales(pagina)
    _renglones(pagina)
    _totales(pagina)
    if modelo['pagos']:
        _pagos(pagina)
        _resumen(pagina)
    _leyendas(pagina)
    return bytes(pdf.output())
