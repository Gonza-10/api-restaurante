"""Vencimientos (hito 6): aviso de lotes por vencer, baja de los vencidos y dias de aviso configurables.

- Un lote se puede usar hasta el dia de su vencimiento inclusive; al dia siguiente esta vencido.
- Los lotes vencidos se dan de baja como perdida con motivo 'vencimiento', al costo real del lote: automaticamente al
  abrir cada jornada y a mano cuando se quiera (boton). Nunca desaparecen en silencio: quedan en perdidas y en el libro.
- Los dias de aviso (5 por defecto) los cambian Admin y Gerente; el aviso se vuelve a calcular en cada consulta, asi
  que muestra siempre cuantos dias faltan.
"""
from django.utils import timezone

from .models import Configuracion, LoteInsumo
from .stock import LoteNoActivo, dar_baja_lote
from .stock_calculos import (
    CERO, DIAS_AVISO_POR_DEFECTO, MAX_DIAS_AVISO, MIN_DIAS_AVISO, MOTIVO_VENCIMIENTO, clave_vencimiento, dias_restantes,
    estado_vencimiento, redondear_dinero, texto_cantidad, texto_dias_vencimiento,
)

CLAVE_DIAS_AVISO = 'dias_aviso_vencimiento'


def dias_aviso():
    """Dias de anticipacion con que se avisa que un lote esta por vencer."""
    fila = Configuracion.objects.filter(clave=CLAVE_DIAS_AVISO).first()
    try:
        valor = int(fila.valor) if fila else DIAS_AVISO_POR_DEFECTO
    except ValueError:
        return DIAS_AVISO_POR_DEFECTO
    return min(max(valor, MIN_DIAS_AVISO), MAX_DIAS_AVISO)


def fijar_dias_aviso(valor, empleado):
    Configuracion.objects.update_or_create(
        clave=CLAVE_DIAS_AVISO,
        defaults={'valor': str(int(valor)), 'empleado': empleado, 'actualizado_en': timezone.now()},
    )
    return int(valor)


def _fila(lote, dias, estado, ve_costos):
    insumo = lote.insumo
    fila = {
        'lote': lote.id,
        'insumo': lote.insumo_id,
        'insumo_nombre': insumo.nombre,
        'tipo_medida': insumo.tipo_medida,
        'origen': lote.origen,
        'cantidad': lote.cantidad_actual,
        'cantidad_texto': texto_cantidad(lote.cantidad_actual, insumo.tipo_medida),
        'fecha_vencimiento': lote.fecha_vencimiento,
        'dias_restantes': dias,
        'estado': estado,
        'texto': texto_dias_vencimiento(dias),
    }
    if ve_costos:
        fila['valor'] = redondear_dinero(lote.cantidad_actual * lote.costo_unitario)
        fila['costo_completo'] = lote.costo_unitario > 0
    return fila


def lotes_con_vencimiento_cercano(ve_costos=False, hoy=None):
    """Lotes activos con stock que ya vencieron o vencen dentro de los dias de aviso, el que vence antes primero.
    Devuelve (vencidos, por_vencer, dias_aviso)."""
    hoy = hoy or timezone.localdate()
    aviso = dias_aviso()
    lotes = (
        LoteInsumo.objects.filter(estado='Activo', cantidad_actual__gt=0, fecha_vencimiento__isnull=False)
        .select_related('insumo').order_by('fecha_vencimiento', 'id')
    )
    vencidos, por_vencer = [], []
    for lote in lotes:
        dias = dias_restantes(lote.fecha_vencimiento, hoy)
        estado = estado_vencimiento(dias, aviso)
        if estado is None:
            continue
        (vencidos if estado == 'vencido' else por_vencer).append(_fila(lote, dias, estado, ve_costos))
    vencidos.sort(key=clave_vencimiento)
    por_vencer.sort(key=clave_vencimiento)
    return vencidos, por_vencer, aviso


def armar_vencimientos(ve_costos, hoy=None):
    """GET /vencimientos: lo que ya vencio (y falta dar de baja) y lo que esta por vencer, con los dias que faltan."""
    hoy = hoy or timezone.localdate()
    vencidos, por_vencer, aviso = lotes_con_vencimiento_cercano(ve_costos, hoy)
    return {
        'hoy': hoy,
        'dias_aviso': aviso,
        'resumen': {'vencidos': len(vencidos), 'por_vencer': len(por_vencer)},
        'vencidos': vencidos,
        'por_vencer': por_vencer,
    }


def procesar_vencidos(empleado, motivo, ve_costos=True, hoy=None):
    """Da de baja, como perdida con motivo 'vencimiento', todos los lotes activos que ya vencieron. Cada lote va en su
    propia transaccion: si uno falla, los demas igual se procesan. Devuelve {'cantidad', 'lotes', 'valor_total'
    (solo si ve_costos), 'valor_completo'}."""
    hoy = hoy or timezone.localdate()
    candidatos = list(
        LoteInsumo.objects.filter(
            estado='Activo', cantidad_actual__gt=0, fecha_vencimiento__isnull=False, fecha_vencimiento__lt=hoy
        ).select_related('insumo').order_by('fecha_vencimiento', 'id')
    )
    dados_de_baja = []
    valor_total = CERO
    completo = True
    for lote in candidatos:
        fila = _fila(lote, dias_restantes(lote.fecha_vencimiento, hoy), 'vencido', True)
        try:
            dar_baja_lote(lote.id, empleado, motivo, MOTIVO_VENCIMIENTO)
        except LoteNoActivo:
            continue  # otro se adelanto (por ejemplo, el boton y la apertura a la vez)
        except Exception as error:
            print(f'[ERROR] No se pudo dar de baja el lote {lote.id} vencido: {error}')
            continue
        valor_total += fila['valor']
        completo = completo and fila['costo_completo']
        if not ve_costos:
            fila.pop('valor', None)
            fila.pop('costo_completo', None)
        dados_de_baja.append(fila)
    resultado = {'cantidad': len(dados_de_baja), 'lotes': dados_de_baja}
    if ve_costos:
        resultado['valor_total'] = redondear_dinero(valor_total)
        resultado['valor_completo'] = completo
    return resultado


def avisos_de_apertura(procesados, por_vencer, aviso):
    """Textos listos para mostrar al abrir la jornada."""
    textos = []
    if procesados['cantidad']:
        detalle = ', '.join(f"{f['insumo_nombre']} ({f['cantidad_texto']})" for f in procesados['lotes'][:5])
        resto = procesados['cantidad'] - 5
        textos.append(
            f"Se dieron de baja {procesados['cantidad']} lote(s) vencido(s): {detalle}" + (f' y {resto} mas.' if resto > 0 else '.')
        )
    for f in por_vencer:
        textos.append(f"{f['insumo_nombre']} (lote {f['lote']}, {f['cantidad_texto']}): {f['texto']}.")
    return textos


def vencimientos_al_abrir(empleado):
    """Lo que pasa con los vencimientos al abrir la jornada (la abre Admin o Gerente, que ven valores): da de baja los
    vencidos y recuerda los que estan por vencer, con los dias que faltan."""
    procesados = procesar_vencidos(empleado, 'Baja automatica por vencimiento al abrir la jornada')
    _, por_vencer, aviso = lotes_con_vencimiento_cercano(ve_costos=True)
    return {
        'dias_aviso': aviso,
        'dados_de_baja': procesados,
        'por_vencer': por_vencer,
        'avisos': avisos_de_apertura(procesados, por_vencer, aviso),
    }
