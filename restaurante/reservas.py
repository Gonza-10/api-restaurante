"""Reservas de mesa (las cargan Admin y Gerente a partir de llamadas y mensajes).

Reglas:
- Una reserva es de una JORNADA: fecha + turno (Almuerzo, Cena...). No tiene duracion: bloquea la mesa toda la jornada.
- Una sola reserva Confirmada por mesa y jornada (lo garantiza ademas un indice unico en la base).
- Una mesa con reserva Confirmada en la jornada abierta solo se abre para esa reserva (el mozo elige la reserva al abrir).
  Nadie la abre para otra persona, ni siquiera Admin o Gerente: si el cliente avisa que no viene, se cancela la reserva.
- Al abrir la mesa por la reserva, pasa a Cumplida y queda ligada a la sesion.
- Tolerancia de llegada (30 minutos por defecto, RESERVA_TOLERANCIA_MINUTOS): pasada la hora acordada mas la tolerancia, la
  reserva pasa sola a "No se presentó" y la mesa queda libre. No hay proceso aparte: se aplica cada vez que se abre una mesa o se
  consultan mesas y reservas (vencer_reservas).
- Se puede reservar una mesa en particular o dejar que el sistema elija la mas chica que alcance.
"""
from decouple import config
from django.db import IntegrityError, transaction
from django.utils import timezone

from .jornadas import jornada_abierta
from .models import Mesa, Reserva
from .reservas_calculos import (
    CANCELADA, CONFIRMADA, CUMPLIDA, NO_SE_PRESENTO, TOLERANCIA_MINUTOS_DEFECTO,
    elegir_mesa, esta_vencida, hora_en_turno, limite_de_llegada, mensaje_mesa_ocupada_para_reservar,
    mensaje_reserva_existente, momento_llegada, texto_hora,
)


class ReglaReserva(Exception):
    """Una regla de las reservas impide la operacion. Mensaje listo para mostrar; `estado` es el codigo HTTP (409 por defecto)."""

    def __init__(self, mensaje, estado=409, **extra):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.estado = estado
        self.extra = extra


class ReservaNoVigente(Exception):
    """La reserva dejo de estar Confirmada mientras se abria la mesa (se cancelo o vencio justo antes)."""


def tolerancia_minutos():
    return config('RESERVA_TOLERANCIA_MINUTOS', default=TOLERANCIA_MINUTOS_DEFECTO, cast=int)


def ahora_local():
    """Hora local actual, sin zona (para comparar con las horas de las reservas)."""
    return timezone.localtime().replace(tzinfo=None)


def llegada_de(reserva):
    turno = reserva.turno
    return momento_llegada(reserva.fecha, reserva.hora, turno.hora_apertura, turno.hora_cierre)


def vencer_reservas():
    """Pasa a 'No se presentó' las reservas Confirmadas cuya hora de llegada mas la tolerancia ya pasaron. Devuelve cuantas."""
    ahora = ahora_local()
    tolerancia = tolerancia_minutos()
    vencidas = [
        r.id for r in Reserva.objects.select_related('turno').filter(estado=CONFIRMADA, fecha__lte=ahora.date())
        if esta_vencida(llegada_de(r), ahora, tolerancia)
    ]
    if not vencidas:
        return 0
    return Reserva.objects.filter(id__in=vencidas, estado=CONFIRMADA).update(
        estado=NO_SE_PRESENTO, fecha_hora_resolucion=timezone.now())


def reserva_bloqueante(mesa_id, jornada):
    """La reserva Confirmada que bloquea la mesa en la jornada dada (o None). Llamar despues de vencer_reservas()."""
    if jornada is None:
        return None
    return (Reserva.objects.select_related('turno')
            .filter(mesa_id=mesa_id, fecha=jornada.fecha, turno_id=jornada.turno_id, estado=CONFIRMADA).first())


def reservas_bloqueantes_por_mesa(jornada):
    """{id_mesa: reserva} de las mesas bloqueadas en la jornada dada. Llamar despues de vencer_reservas()."""
    if jornada is None:
        return {}
    reservas = (Reserva.objects.select_related('turno')
                .filter(fecha=jornada.fecha, turno_id=jornada.turno_id, estado=CONFIRMADA, mesa__isnull=False))
    return {r.mesa_id: r for r in reservas}


def _validar_horario(fecha, turno, hora):
    if not turno.activo:
        raise ReglaReserva('Ese turno está dado de baja.', 400)
    if not hora_en_turno(turno.hora_apertura, turno.hora_cierre, hora):
        raise ReglaReserva(
            f'La hora debe estar dentro del horario del turno {turno.nombre} '
            f'({texto_hora(turno.hora_apertura)} a {texto_hora(turno.hora_cierre)}).', 400)
    if momento_llegada(fecha, hora, turno.hora_apertura, turno.hora_cierre) < ahora_local():
        raise ReglaReserva('No se puede reservar en el pasado.', 400)


def _mesas_ocupadas_ahora(fecha, turno):
    """Numeros de mesa que no se pueden reservar porque estan ocupadas en la jornada abierta que coincide con (fecha, turno)."""
    jornada = jornada_abierta()
    if jornada is None or jornada.fecha != fecha or jornada.turno_id != turno.id:
        return set()
    return set(Mesa.objects.filter(activa=True, estado=True).values_list('id', flat=True))


def _mesas_libres(fecha, turno, personas, excluir_reserva_id=None):
    """Mesas activas con capacidad suficiente y sin reserva Confirmada ni ocupacion en esa jornada, de la mas chica a la mas grande."""
    tomadas = set(Reserva.objects.filter(fecha=fecha, turno=turno, estado=CONFIRMADA, mesa__isnull=False)
                  .exclude(id=excluir_reserva_id or 0).values_list('mesa_id', flat=True))
    tomadas |= _mesas_ocupadas_ahora(fecha, turno)
    return [m for m in Mesa.objects.filter(activa=True, capacidad_maxima__gte=personas).order_by('capacidad_maxima', 'numero')
            if m.id not in tomadas]


def disponibilidad(fecha, turno, personas):
    """Mesas libres para una jornada y una cantidad de personas, con la sugerida (la mas chica que alcanza)."""
    vencer_reservas()
    mesas = _mesas_libres(fecha, turno, personas)
    sugerida = elegir_mesa([(m.numero, m.capacidad_maxima) for m in mesas], personas)
    return mesas, sugerida


def _resolver_mesa(fecha, turno, personas, numero_mesa, excluir_reserva_id=None):
    """La mesa de la reserva: la pedida (con todas las validaciones) o la mas chica libre que alcance."""
    if numero_mesa is None:
        mesas = _mesas_libres(fecha, turno, personas, excluir_reserva_id)
        numero = elegir_mesa([(m.numero, m.capacidad_maxima) for m in mesas], personas)
        if numero is None:
            raise ReglaReserva(f'No hay ninguna mesa libre para {personas} personas en ese turno y fecha.')
        return next(m for m in mesas if m.numero == numero)
    mesa = Mesa.objects.filter(numero=numero_mesa, activa=True).first()
    if mesa is None:
        raise ReglaReserva(f'No existe la mesa número {numero_mesa}.', 404)
    if personas > mesa.capacidad_maxima:
        raise ReglaReserva(f'La mesa {mesa.numero} admite hasta {mesa.capacidad_maxima} personas.', 400)
    existente = (Reserva.objects.select_related('turno')
                 .filter(mesa=mesa, fecha=fecha, turno=turno, estado=CONFIRMADA)
                 .exclude(id=excluir_reserva_id or 0).first())
    if existente:
        raise ReglaReserva(mensaje_reserva_existente(mesa.numero, existente.nombre, existente.apellido, turno.nombre, fecha))
    if mesa.id in _mesas_ocupadas_ahora(fecha, turno):
        raise ReglaReserva(mensaje_mesa_ocupada_para_reservar(mesa.numero))
    return mesa


def crear_reserva(datos, empleado):
    """`datos`: nombre, apellido, telefono, fecha, turno (objeto Turno), hora, cantidad_personas, numero_mesa (opcional),
    notas, origen. Lanza ReglaReserva. Devuelve la Reserva creada."""
    vencer_reservas()
    turno = datos['turno']
    _validar_horario(datos['fecha'], turno, datos['hora'])
    mesa = _resolver_mesa(datos['fecha'], turno, datos['cantidad_personas'], datos.get('numero_mesa'))
    try:
        with transaction.atomic():
            return Reserva.objects.create(
                nombre=datos['nombre'], apellido=datos['apellido'], telefono=datos['telefono'],
                fecha=datos['fecha'], hora=datos['hora'], turno=turno, cantidad_personas=datos['cantidad_personas'],
                mesa=mesa, empleado=empleado, estado=CONFIRMADA,
                notas=datos.get('notas') or None, origen=datos.get('origen') or None,
            )
    except IntegrityError:
        # otra reserva tomo la misma mesa y jornada al mismo tiempo (lo frena el indice unico de la base)
        raise ReglaReserva(f'La mesa {mesa.numero} acaba de ser reservada para ese turno y fecha. Elegí otra.')


def actualizar_reserva(reserva, cambios):
    """Edita una reserva Confirmada. `cambios` trae solo los campos a modificar (los mismos que crear_reserva).
    Si cambia fecha, turno, hora, personas o mesa se vuelven a validar todas las reglas."""
    vencer_reservas()
    reserva.refresh_from_db()
    if reserva.estado != CONFIRMADA:
        raise ReglaReserva(f'No se puede editar una reserva en estado «{reserva.estado}».')
    fecha = cambios.get('fecha', reserva.fecha)
    turno = cambios.get('turno', reserva.turno)
    hora = cambios.get('hora', reserva.hora)
    personas = cambios.get('cantidad_personas', reserva.cantidad_personas)
    cambia_horario = any(k in cambios for k in ('fecha', 'turno', 'hora'))
    cambia_mesa = 'numero_mesa' in cambios or 'cantidad_personas' in cambios or cambia_horario
    if cambia_horario:
        _validar_horario(fecha, turno, hora)
    mesa = reserva.mesa
    if cambia_mesa:
        pedida = cambios.get('numero_mesa', mesa.numero if mesa else None)
        # al cambiar de jornada o de personas se conserva la mesa solo si sigue sirviendo; si el usuario no pidio una, se elige otra
        mesa = _resolver_mesa(fecha, turno, personas, pedida, excluir_reserva_id=reserva.id)
    for campo in ('nombre', 'apellido', 'telefono', 'notas', 'origen'):
        if campo in cambios:
            setattr(reserva, campo, (cambios[campo] or None) if campo in ('notas', 'origen') else cambios[campo])
    reserva.fecha, reserva.turno, reserva.hora, reserva.cantidad_personas, reserva.mesa = fecha, turno, hora, personas, mesa
    try:
        with transaction.atomic():
            reserva.save()
    except IntegrityError:
        raise ReglaReserva(f'La mesa {mesa.numero} acaba de ser reservada para ese turno y fecha. Elegí otra.')
    return reserva


def cancelar_reserva(reserva, empleado, motivo=None):
    """Cancela una reserva Confirmada (el cliente avisó que no viene). Libera la mesa."""
    vencer_reservas()
    reserva.refresh_from_db()
    if reserva.estado != CONFIRMADA:
        raise ReglaReserva(f'Solo se cancelan reservas confirmadas (esta está «{reserva.estado}»).')
    reserva.estado = CANCELADA
    reserva.fecha_hora_cancelacion = timezone.now()
    reserva.empleado_cancelacion = empleado
    reserva.motivo_cancelacion = (motivo or '').strip()[:200] or None
    reserva.save(update_fields=['estado', 'fecha_hora_cancelacion', 'empleado_cancelacion', 'motivo_cancelacion'])
    return reserva


def cumplir_reserva(reserva_id, sesion):
    """Marca la reserva como Cumplida y la liga a la sesion. Se llama DENTRO de la transaccion que abre la mesa: si la reserva
    ya no estaba Confirmada, lanza ReservaNoVigente y la apertura se deshace."""
    actualizadas = Reserva.objects.filter(id=reserva_id, estado=CONFIRMADA).update(
        estado=CUMPLIDA, fecha_hora_resolucion=timezone.now(), pedido_cabecera=sesion)
    if actualizadas == 0:
        raise ReservaNoVigente()


def limite_de_espera(reserva):
    """Fecha y hora hasta la que se espera al cliente (hora de llegada mas tolerancia)."""
    return limite_de_llegada(llegada_de(reserva), tolerancia_minutos())
