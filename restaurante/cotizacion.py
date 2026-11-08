"""Cotizacion oficial de USD, BRL y PYG (cobros, hito 1).

- La fuente es la API de Estadisticas Cambiarias del BCRA (campo `tipoCotizacion`: ARS por 1 unidad de la moneda).
  Nadie carga cotizaciones a mano: ni Admin ni Gerente (decision de David: seria deshonesto).
- worker_cotizacion.py llama a actualizar_cotizaciones() cada 30 minutos. Solo se guarda una fila nueva cuando el valor
  cambio; la vigente es la ultima de cada moneda.
- Fines de semana y feriados el BCRA no publica: se busca el ultimo dia con datos y, si no hay conexion, sigue vigente la
  ultima cotizacion guardada (respaldo). Cada pago en efectivo congela la cotizacion que uso (hito 3).
- Solo libreria estandar para la consulta (urllib), asi no se suma ninguna dependencia. Se verifica el certificado TLS.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime

from decouple import config
from django.db import transaction
from django.utils import timezone

from .cobros_calculos import (
    MONEDA_BASE, MONEDAS_EXTRANJERAS, RespuestaBcraInvalida, esta_desactualizada, fechas_a_consultar, necesita_guardar,
    parsear_cotizaciones_bcra,
)
from .models import Configuracion, CotizacionMoneda

URL_BCRA = config('BCRA_URL', default='https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones')
TIMEOUT_SEGUNDOS = 10
FUENTE = 'BCRA'

CLAVE_ULTIMA_CONSULTA = 'cotizacion_ultima_consulta'   # momento de la ultima consulta exitosa (ISO 8601)
CLAVE_ULTIMO_ERROR = 'cotizacion_ultimo_error'         # texto del ultimo error ('' si la ultima consulta salio bien)


class BcraNoDisponible(Exception):
    """No se pudo obtener una cotizacion del BCRA (sin conexion, error del servidor, certificado o respuesta rara)."""


# ---------- consulta al BCRA ----------

def _pedir_json(url):
    pedido = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'SavageGrill/1.0'})
    with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS) as respuesta:
        return json.loads(respuesta.read().decode('utf-8'))


def consultar_bcra(hoy=None):
    """Busca las cotizaciones de USD, BRL y PYG empezando por hoy y retrocediendo dia por dia (el BCRA no publica los
    fines de semana ni feriados). Cada moneda se toma del dia mas reciente que la traiga.
    Devuelve {moneda: (fecha, valor)}. Lanza BcraNoDisponible si no hay conexion, el servidor falla o no se encuentra
    ninguna cotizacion en los ultimos dias."""
    hoy = hoy or timezone.localdate()
    encontradas = {}
    for fecha in fechas_a_consultar(hoy):
        try:
            datos = _pedir_json(f'{URL_BCRA}?fecha={fecha.isoformat()}')
        except urllib.error.HTTPError as error:
            if error.code in (400, 404):   # ese dia no tiene datos: se prueba el anterior
                continue
            raise BcraNoDisponible(f'El BCRA respondio con error {error.code}.') from error
        except (urllib.error.URLError, OSError, ValueError) as error:   # sin red, tiempo agotado, certificado, JSON roto
            raise BcraNoDisponible(f'No se pudo consultar al BCRA: {error}') from error
        try:
            fecha_datos, valores = parsear_cotizaciones_bcra(datos)
        except RespuestaBcraInvalida as error:
            raise BcraNoDisponible(f'Respuesta inesperada del BCRA: {error}') from error
        for moneda, valor in valores.items():
            encontradas.setdefault(moneda, (fecha_datos or fecha, valor))
        if all(m in encontradas for m in MONEDAS_EXTRANJERAS):
            break
    if not encontradas:
        raise BcraNoDisponible('El BCRA no publico cotizaciones en los ultimos dias consultados.')
    return encontradas


# ---------- lo guardado ----------

def ultima_cotizacion(moneda):
    """La cotizacion vigente de una moneda (la ultima guardada), o None si todavia no hay ninguna."""
    return CotizacionMoneda.objects.filter(moneda=moneda).order_by('-fecha_hora', '-id').first()


def cotizaciones_vigentes():
    """{moneda: Decimal ARS por unidad} de las monedas que ya tienen cotizacion guardada."""
    vigentes = {}
    for moneda in MONEDAS_EXTRANJERAS:
        fila = ultima_cotizacion(moneda)
        if fila is not None:
            vigentes[moneda] = fila.valor
    return vigentes


def _leer_config(clave):
    fila = Configuracion.objects.filter(clave=clave).first()
    return fila.valor if fila else None


def _guardar_config(clave, valor, ahora):
    Configuracion.objects.update_or_create(
        clave=clave, defaults={'valor': str(valor)[:190], 'empleado': None, 'actualizado_en': ahora},
    )


def _momento(texto):
    try:
        return datetime.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def actualizar_cotizaciones():
    """Consulta al BCRA y guarda lo que cambio. Devuelve {'guardadas': [monedas], 'sin_cambios': [monedas]}.
    Si falla deja registrado el error y lanza BcraNoDisponible: las cotizaciones ya guardadas siguen vigentes."""
    ahora = timezone.now()
    try:
        encontradas = consultar_bcra()
    except BcraNoDisponible as error:
        _guardar_config(CLAVE_ULTIMO_ERROR, error, ahora)
        raise

    guardadas, sin_cambios = [], []
    with transaction.atomic():
        for moneda in sorted(encontradas):
            fecha, valor = encontradas[moneda]
            ultima = ultima_cotizacion(moneda)
            if necesita_guardar(ultima.valor if ultima else None, valor):
                CotizacionMoneda.objects.create(moneda=moneda, valor=valor, fecha=fecha, fuente=FUENTE, fecha_hora=ahora)
                guardadas.append(moneda)
            else:
                sin_cambios.append(moneda)
        _guardar_config(CLAVE_ULTIMA_CONSULTA, ahora.isoformat(), ahora)
        _guardar_config(CLAVE_ULTIMO_ERROR, '', ahora)
    return {'guardadas': guardadas, 'sin_cambios': sin_cambios}


def estado_cotizaciones(con_detalle_error=False):
    """Lo que muestra GET /cotizaciones. El texto del ultimo error solo se incluye para Admin y Gerente."""
    ahora = timezone.now()
    filas = []
    for moneda in MONEDAS_EXTRANJERAS:
        fila = ultima_cotizacion(moneda)
        filas.append({
            'moneda': moneda,
            'valor': fila.valor if fila else None,
            'fecha': fila.fecha if fila else None,
            'actualizada_en': fila.fecha_hora if fila else None,
            'fuente': fila.fuente if fila else None,
        })
    ultima_consulta = _momento(_leer_config(CLAVE_ULTIMA_CONSULTA))
    estado = {
        'moneda_base': MONEDA_BASE,
        'unidad': 'ARS por 1 unidad de la moneda',
        'cotizaciones': filas,
        'ultima_consulta': ultima_consulta,
        'desactualizada': esta_desactualizada(ultima_consulta, ahora),
    }
    if con_detalle_error:
        estado['ultimo_error'] = _leer_config(CLAVE_ULTIMO_ERROR) or None
    return estado
