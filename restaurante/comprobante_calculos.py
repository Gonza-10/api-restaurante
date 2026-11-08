"""Calculos puros del comprobante PDF de la factura (cobros, hito 6): sin base de datos, sin Django y sin la libreria de PDF.
Aca se decide QUE dice el comprobante (importes con formato argentino, nombre del archivo, validacion de la casilla
"quiero factura"); `comprobante_pdf.py` solo lo dibuja y `comprobante.py` junta los datos de la base."""
import re
from decimal import Decimal, ROUND_HALF_UP

CERO = Decimal('0')
MEDIOS = {'Efectivo': 'Efectivo', 'MercadoPago': 'Mercado Pago'}
MONEDAS_SIN_DECIMALES = ('PYG',)
NOMBRE_MAX = 100
ARCHIVO_MAX = 80
LEYENDA_FISCAL = 'Comprobante interno de consumo. No es una factura fiscal ni reemplaza la emitida ante ARCA.'

# La fuente estandar de los PDF (Helvetica) solo conoce Latin-1: lo demas se reemplaza para que el PDF no falle.
_REEMPLAZOS = {
    '–': '-', '—': '-', '−': '-', '‘': "'", '’': "'", '“': '"', '”': '"',
    '•': '-', '…': '...', '€': 'EUR', '₲': 'Gs', ' ': ' ', '\t': ' ',
}
_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
_NO_ARCHIVO = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
_ESPACIOS = re.compile(r'\s+')


class PedidoInvalido(ValueError):
    """La casilla "quiero factura" vino mal. `campo` dice cual."""

    def __init__(self, campo, mensaje):
        super().__init__(mensaje)
        self.campo = campo


# ---------- textos ----------

def texto_pdf(valor, largo=None):
    """Texto seguro para el PDF: sin caracteres de control, con los simbolos no Latin-1 reemplazados, en una sola linea."""
    texto = '' if valor is None else str(valor)
    for origen, destino in _REEMPLAZOS.items():
        texto = texto.replace(origen, destino)
    texto = _CONTROL.sub(' ', texto)
    texto = _ESPACIOS.sub(' ', texto).strip()
    texto = texto.encode('latin-1', 'replace').decode('latin-1')
    if largo is not None and len(texto) > largo:
        texto = texto[:largo - 1].rstrip() + '.'
    return texto


def _miles(entero):
    return f'{entero:,}'.replace(',', '.')


def numero_ar(monto, decimales=2):
    """1234.5 -> '1.234,50' (puntos de miles y coma decimal)."""
    valor = Decimal(str(monto)).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    negativo = valor < 0
    entero, _, fraccion = f'{abs(valor):f}'.partition('.')
    texto = _miles(int(entero))
    if decimales:
        texto += ',' + fraccion.ljust(decimales, '0')[:decimales]
    return ('-' if negativo else '') + texto


def pesos(monto):
    return '$ ' + numero_ar(monto)


def importe(monto, moneda='ARS'):
    """'$ 1.234,50' para pesos; 'USD 12,34' para las otras (el guarani no tiene centavos)."""
    if monto is None:
        return '-'
    if moneda == 'ARS':
        return pesos(monto)
    return f"{moneda} {numero_ar(monto, 0 if moneda in MONEDAS_SIN_DECIMALES else 2)}"


def cotizacion_texto(moneda, valor):
    """'1 USD = $ 1.200,50'. Las monedas que valen menos de un peso (guarani) llevan 4 decimales para no perder precision."""
    valor = Decimal(str(valor))
    return f"1 {moneda} = $ {numero_ar(valor, 4 if valor < 10 else 2)}"


def fecha_hora(valor):
    return valor.strftime('%d/%m/%Y %H:%M') if valor else '-'


def numero_de_factura(id_factura):
    return f'N° {int(id_factura):08d}'


# ---------- nombre del archivo ----------

def limpiar_nombre(nombre):
    """El nombre que escribio el cliente, sin lo que un sistema de archivos no admite."""
    texto = _NO_ARCHIVO.sub(' ', '' if nombre is None else str(nombre))
    texto = _ESPACIOS.sub(' ', texto).strip(' .')
    return texto[:ARCHIVO_MAX].rstrip(' .')


def nombre_archivo(nombre_cliente, numero_mesa, fecha):
    """'David - 08-11-26.pdf'. Las barras no se pueden usar en un nombre de archivo, por eso la fecha lleva guiones.
    Sin nombre (no deberia pasar: es obligatorio al pedir la factura) queda 'Mesa 5 - 08-11-26.pdf'."""
    base = limpiar_nombre(nombre_cliente) or f'Mesa {numero_mesa}'
    return f"{base} - {fecha.strftime('%d-%m-%y')}.pdf"


def nombre_guardado(nombre_cliente, numero_mesa, fecha, id_factura):
    """El nombre con el que el comprobante se guarda en la carpeta `Facturas/`: 'David - 08-11-26 (factura 7).pdf'. Lleva el numero
    de factura para que dos clientes con el mismo nombre el mismo dia no se pisen, y para poder reemplazar o borrar
    exactamente el archivo de esa factura. (El nombre de la descarga, en cambio, no lo lleva: ver `nombre_archivo`.)"""
    return nombre_archivo(nombre_cliente, numero_mesa, fecha)[:-len('.pdf')] + sufijo_guardado(id_factura)


def sufijo_guardado(id_factura):
    return f' (factura {int(id_factura)}).pdf'


# ---------- la casilla "quiero factura" ----------

_VERDADERO = ('true', '1', 'si', 'sí', 'yes', 'on')
_FALSO = ('false', '0', 'no', 'off')


def _booleano(valor):
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    if texto in _VERDADERO:
        return True
    if texto in _FALSO:
        return False
    raise PedidoInvalido('quiere_factura', 'Debe ser verdadero o falso.')


def validar_pedido_de_factura(datos):
    """Lee {"quiere_factura": true, "nombre_factura": "David"} de lo que mando el cliente o el mozo.
    Devuelve None si no vino la casilla (no cambia nada) o (quiere, nombre). Si la tilda, el nombre es obligatorio; si la
    destilda, el nombre se borra."""
    if not isinstance(datos, dict) or datos.get('quiere_factura') in (None, ''):
        return None
    quiere = _booleano(datos['quiere_factura'])
    if not quiere:
        return False, None
    nombre = _ESPACIOS.sub(' ', _CONTROL.sub(' ', str(datos.get('nombre_factura') or ''))).strip()
    if not nombre:
        raise PedidoInvalido('nombre_factura', 'Para pedir la factura hay que indicar el nombre de quien paga.')
    if len(nombre) > NOMBRE_MAX:
        raise PedidoInvalido('nombre_factura', f'Admite hasta {NOMBRE_MAX} caracteres.')
    return True, nombre


# ---------- armado del contenido ----------

def _fila_pago(pago):
    moneda = pago['moneda']
    recibido = importe(pago['monto_recibido'] if pago.get('monto_recibido') is not None else pago['monto'], moneda)
    cotizacion = ''
    if moneda != 'ARS' and pago.get('cotizacion'):
        cotizacion = cotizacion_texto(moneda, pago['cotizacion'])
    return {
        'fecha': fecha_hora(pago['fecha_hora']),
        'medio': MEDIOS.get(pago['medio'], pago['medio']),
        'recibido': recibido,
        'cotizacion': cotizacion,
        'cuenta': pesos(pago['monto']),
        'propina': pesos(pago['propina']) if pago['propina'] else '-',
        'vuelto': pesos(pago['vuelto']) if pago['vuelto'] else '-',
    }


def armar_modelo(datos):
    """De los datos crudos de la factura al contenido final, todo ya en texto. `datos`:
      factura: id, estado, emision, pago (datetimes locales), total (Decimal); cliente; mesa; comensales; mozo (o None)
      renglones: [{cantidad, descripcion, precio_unitario, sub_total}]
      equivalentes / cotizaciones: {'USD': Decimal|None, 'BRL': ..., 'PYG': ...}
      pagos: [{fecha_hora, medio, moneda, monto_recibido, cotizacion, monto, propina, vuelto}] (solo los aprobados)
    """
    pagos = datos['pagos']
    total = datos['total']
    propina = sum((p['propina'] for p in pagos), CERO)
    vuelto = sum((p['vuelto'] for p in pagos), CERO)
    cobrado = sum((p['monto'] for p in pagos), CERO)

    generales = [('Cliente', texto_pdf(datos['cliente'], NOMBRE_MAX)), ('Mesa', str(datos['mesa'])),
                 ('Comensales', str(datos['comensales']))]
    if datos.get('mozo'):
        generales.append(('Atendió', texto_pdf(datos['mozo'], 60)))
    generales += [('Emitida', fecha_hora(datos['emision'])), ('Pagada', fecha_hora(datos.get('pago')))]

    equivalentes = []
    for moneda in ('USD', 'BRL', 'PYG'):
        valor = datos['equivalentes'].get(moneda)
        if valor is None:
            continue
        cot = datos['cotizaciones'].get(moneda)
        equivalentes.append({
            'moneda': moneda, 'importe': importe(valor, moneda),
            'cotizacion': cotizacion_texto(moneda, cot) if cot else '',
        })

    resumen = [('Total de la cuenta', pesos(total))]
    if propina:
        resumen.append(('Propina', pesos(propina)))
    resumen.append(('Total cobrado', pesos(cobrado + propina)))
    if vuelto:
        resumen.append(('Vuelto entregado', pesos(vuelto)))

    return {
        'marca': ('SAVAGE', 'GRILL'),
        'titulo': 'COMPROBANTE DE CONSUMO',
        'numero': numero_de_factura(datos['id']),
        'estado': str(datos['estado']).upper(),
        'generales': generales,
        'renglones': [
            {'cantidad': str(r['cantidad']), 'descripcion': texto_pdf(r['descripcion']),
             'unitario': pesos(r['precio_unitario']), 'subtotal': pesos(r['sub_total'])}
            for r in datos['renglones']
        ],
        'total': pesos(total),
        'equivalentes': equivalentes,
        'pagos': [_fila_pago(p) for p in pagos],
        'resumen': resumen,
        'leyendas': [LEYENDA_FISCAL, 'Gracias por visitarnos.'],
    }


def partir_texto(texto, ancho_maximo, medir):
    """Parte un texto en renglones que no pasen de `ancho_maximo` (segun `medir(texto)`), cortando por palabras; una palabra
    mas larga que el renglon se corta donde haga falta. Siempre devuelve al menos un renglon."""
    renglones, actual = [], ''
    for palabra in str(texto).split(' '):
        while palabra and medir(palabra) > ancho_maximo:     # palabra que no entra ni sola
            if actual:
                renglones.append(actual)
                actual = ''
            corte = len(palabra)
            while corte > 1 and medir(palabra[:corte]) > ancho_maximo:
                corte -= 1
            renglones.append(palabra[:corte])
            palabra = palabra[corte:]
        candidato = palabra if not actual else f'{actual} {palabra}'
        if medir(candidato) <= ancho_maximo:
            actual = candidato
        else:
            renglones.append(actual)
            actual = palabra
    renglones.append(actual)
    return [r for r in renglones if r != ''] or ['']
