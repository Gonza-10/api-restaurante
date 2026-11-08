"""Comprobante PDF de la factura (cobros, hito 6).

- La factura interna se emite siempre (hace falta para cobrar). Lo opcional es el PDF: el cliente tilda "quiero factura" y
  escribe el nombre de quien paga ANTES de pagar (o el mozo lo hace por el, en el salon). Queda en `Factura.solicito_ticket` y
  `Factura.nombre_factura`, y se puede corregir mientras la factura siga vigente.
- Es UN comprobante por factura (por mesa), con todo: los renglones, cada pago (medio, moneda, vuelto, propina) y lo que
  equivale el total en USD, BRL y PYG con las cotizaciones congeladas al emitirla.
- Se descarga cuando la factura esta Pagada. Todo lo que muestra esta congelado en la base, asi que sale siempre igual, y si
  despues se anula un pago deja de estar disponible.
- Ademas, al quedar Pagada una factura que se pidio, el PDF se guarda en la carpeta `Facturas/` (aparte de `tickets/`, donde van
  los tickets de cada comanda) como 'David - 08-11-26 (factura 7).pdf'. Si la factura deja de estar Pagada o se
  destilda la casilla, el archivo se borra. Guardarlo nunca puede hacer fallar un cobro: si no se puede, se anota en el log.
"""
import logging
import os

from django.utils import timezone

from .comprobante_calculos import armar_modelo, nombre_archivo, nombre_guardado, sufijo_guardado
from .comprobante_pdf import dibujar
from .cuenta import ReglaCuenta
from .models import Factura, FacturaDetalle, Pago

logger = logging.getLogger(__name__)
CARPETA_FACTURAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Facturas')   # junto a tickets/, en la raiz
try:
    os.makedirs(CARPETA_FACTURAS, exist_ok=True)   # existe desde que arranca el servidor, no recien al guardar la primera factura
except OSError:
    logger.exception('No se pudo crear la carpeta %s', CARPETA_FACTURAS)


def _local(valor):
    """Fecha y hora en la zona horaria del local (la base las guarda en UTC)."""
    if valor is not None and timezone.is_aware(valor):
        return timezone.localtime(valor)
    return valor


def _nombre(empleado):
    return f'{empleado.nombre} {empleado.apellido}' if empleado else None


def fijar_pedido(factura_id, quiere, nombre):
    """Guarda la casilla "quiero factura" y el nombre. Si la destilda, el nombre se borra. Devuelve la factura."""
    factura = Factura.objects.get(pk=factura_id)
    if factura.estado == 'Anulada':
        raise ReglaCuenta('La factura esta anulada: no admite comprobante.')
    Factura.objects.filter(pk=factura.pk).update(solicito_ticket=quiere, nombre_factura=nombre if quiere else None)
    factura.solicito_ticket, factura.nombre_factura = quiere, (nombre if quiere else None)
    sincronizar_en_facturas(factura.pk)
    return factura


def comprobante_disponible(factura):
    """Lanza ReglaCuenta con el motivo si todavia no se puede descargar."""
    if factura.estado == 'Anulada':
        raise ReglaCuenta('La factura esta anulada: no tiene comprobante.')
    if not factura.solicito_ticket:
        raise ReglaCuenta('No se pidio la factura de esta mesa. Marcar "quiero factura" e indicar el nombre para obtenerla.')
    if factura.estado != 'Pagada':
        raise ReglaCuenta('La factura todavia no esta pagada: el comprobante se descarga cuando se completa el pago.')


def datos_de_factura(factura):
    """Todo lo que muestra el comprobante, leido de lo que quedo congelado en la base."""
    sesion = factura.pedido_cabecera
    renglones = FacturaDetalle.objects.filter(factura=factura).order_by('id')
    pagos = Pago.objects.filter(factura=factura, estado='Aprobado').select_related('metodo_pago').order_by('fecha_hora', 'id')
    return {
        'id': factura.id,
        'estado': factura.estado,
        'emision': _local(factura.fecha_hora_emision),
        'pago': _local(factura.fecha_hora_pago),
        'total': factura.total,
        'cliente': factura.nombre_factura or f'Mesa {sesion.mesa.numero}',
        'mesa': sesion.mesa.numero,
        'comensales': sesion.cantidad_comensales,
        'mozo': _nombre(sesion.empleado),
        'renglones': [
            {'cantidad': r.cantidad, 'descripcion': r.descripcion, 'precio_unitario': r.precio_unitario, 'sub_total': r.sub_total}
            for r in renglones
        ],
        'equivalentes': {'USD': factura.total_usd, 'BRL': factura.total_brl, 'PYG': factura.total_pyg},
        'cotizaciones': {'USD': factura.cotizacion_usd, 'BRL': factura.cotizacion_brl, 'PYG': factura.cotizacion_pyg},
        'pagos': [
            {'fecha_hora': _local(p.fecha_hora), 'medio': p.metodo_pago.nombre, 'moneda': p.moneda, 'monto_recibido': p.monto_recibido,
             'cotizacion': p.cotizacion, 'monto': p.monto, 'propina': p.monto_propina, 'vuelto': p.vuelto}
            for p in pagos
        ],
    }


def generar(factura):
    """(bytes del PDF, nombre del archivo). ReglaCuenta si todavia no corresponde."""
    comprobante_disponible(factura)
    factura = Factura.objects.select_related('pedido_cabecera__mesa', 'pedido_cabecera__empleado').get(pk=factura.pk)
    datos = datos_de_factura(factura)
    fecha = datos['pago'] or datos['emision']
    return dibujar(armar_modelo(datos)), nombre_archivo(factura.nombre_factura, datos['mesa'], fecha)


# ---------- copia en la carpeta Facturas/ ----------

def _borrar_guardados(factura_id):
    sufijo = sufijo_guardado(factura_id)
    if not os.path.isdir(CARPETA_FACTURAS):
        return
    for archivo in os.listdir(CARPETA_FACTURAS):
        if archivo.endswith(sufijo):
            os.remove(os.path.join(CARPETA_FACTURAS, archivo))


def sincronizar_en_facturas(factura_id):
    """Deja en `Facturas/` el comprobante de la factura si corresponde (se pidio y esta Pagada) y lo borra si no. Se llama cada vez
    que cambia lo que lo habilita: al quedar Pagada o dejar de estarlo, y al tildar o destildar la casilla. Devuelve la ruta del
    archivo o None. Nunca lanza: un problema de disco o de PDF no debe deshacer un cobro."""
    try:
        factura = Factura.objects.select_related('pedido_cabecera__mesa', 'pedido_cabecera__empleado').get(pk=factura_id)
        _borrar_guardados(factura.pk)
        try:
            comprobante_disponible(factura)
        except ReglaCuenta:
            return None
        contenido, _ = generar(factura)
        datos = datos_de_factura(factura)
        nombre = nombre_guardado(factura.nombre_factura, datos['mesa'], datos['pago'] or datos['emision'], factura.pk)
        os.makedirs(CARPETA_FACTURAS, exist_ok=True)
        ruta = os.path.join(CARPETA_FACTURAS, nombre)
        with open(ruta, 'wb') as archivo:
            archivo.write(contenido)
        return ruta
    except Exception:
        logger.exception('No se pudo guardar en Facturas/ el comprobante de la factura %s', factura_id)
        return None
