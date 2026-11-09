"""Serializers de reservas: la entrada se valida con DRF y la salida es un dict con el formato que usa el front."""
from rest_framework import serializers

from .models import Turno
from .reservas import limite_de_espera
from .reservas_calculos import ESTADOS, ORIGENES, limpiar_telefono, texto_hora
from .serializers import fecha_iso

_OBLIGATORIO = {'required': 'Campo obligatorio.', 'blank': 'No puede estar vacío.', 'null': 'Campo obligatorio.'}


class ReservaEntradaSerializer(serializers.Serializer):
    """Alta (todos los obligatorios) y edicion (partial=True: solo lo que cambia).
    numero_mesa es opcional: sin ella (o con null) el sistema elige la mesa mas chica libre que alcance."""
    nombre = serializers.CharField(max_length=80, trim_whitespace=True, error_messages=_OBLIGATORIO)
    apellido = serializers.CharField(max_length=80, trim_whitespace=True, error_messages=_OBLIGATORIO)
    telefono = serializers.CharField(max_length=20, error_messages=_OBLIGATORIO)
    fecha = serializers.DateField(error_messages={**_OBLIGATORIO, 'invalid': 'Fecha inválida (formato AAAA-MM-DD).'})
    turno = serializers.IntegerField(min_value=1, error_messages={**_OBLIGATORIO, 'invalid': 'Debe ser el id de un turno.'})
    hora = serializers.TimeField(
        input_formats=['%H:%M', '%H:%M:%S'], error_messages={**_OBLIGATORIO, 'invalid': 'Hora inválida (formato HH:MM).'})
    cantidad_personas = serializers.IntegerField(
        min_value=1, max_value=100,
        error_messages={**_OBLIGATORIO, 'invalid': 'Debe ser un número entero.', 'min_value': 'Debe haber al menos una persona.',
                        'max_value': 'Cantidad de personas demasiado alta.'})
    numero_mesa = serializers.IntegerField(
        min_value=1, required=False, allow_null=True,
        error_messages={'invalid': 'Debe ser un número entero.', 'min_value': 'Debe ser mayor a 0.'})
    notas = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)
    origen = serializers.ChoiceField(
        choices=ORIGENES, required=False, allow_null=True, allow_blank=True,
        error_messages={'invalid_choice': f'Valores válidos: {", ".join(ORIGENES)}.'})

    def validate_telefono(self, valor):
        try:
            return limpiar_telefono(valor)
        except ValueError as error:
            raise serializers.ValidationError(str(error))

    def validate_turno(self, valor):
        turno = Turno.objects.filter(id=valor).first()
        if turno is None:
            raise serializers.ValidationError('No existe ese turno.')
        return turno


class ReservaFiltroSerializer(serializers.Serializer):
    """Filtros de GET /reservas. Sin fechas, lista desde hoy en adelante."""
    fecha = serializers.DateField(required=False)
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    turno = serializers.IntegerField(required=False, min_value=1)
    mesa = serializers.IntegerField(required=False, min_value=1)
    estado = serializers.ChoiceField(choices=ESTADOS, required=False,
                                     error_messages={'invalid_choice': f'Valores válidos: {", ".join(ESTADOS)}.'})


class DisponibilidadFiltroSerializer(serializers.Serializer):
    fecha = serializers.DateField(error_messages={**_OBLIGATORIO, 'invalid': 'Fecha inválida (formato AAAA-MM-DD).'})
    turno = serializers.IntegerField(min_value=1, error_messages=_OBLIGATORIO)
    personas = serializers.IntegerField(min_value=1, max_value=100, error_messages=_OBLIGATORIO)


def _nombre(empleado):
    return f'{empleado.nombre} {empleado.apellido}' if empleado else None


def reserva_a_dict(reserva):
    """Una reserva lista para enviar al front."""
    mesa = reserva.mesa
    cancelacion = None
    if reserva.fecha_hora_cancelacion:
        cancelacion = {
            'fecha_hora': fecha_iso(reserva.fecha_hora_cancelacion),
            'por': _nombre(reserva.empleado_cancelacion),
            'motivo': reserva.motivo_cancelacion,
        }
    return {
        'id': reserva.id,
        'nombre': reserva.nombre,
        'apellido': reserva.apellido,
        'telefono': reserva.telefono,
        'fecha': reserva.fecha.isoformat(),
        'turno': {'id': reserva.turno_id, 'nombre': reserva.turno.nombre},
        'hora': texto_hora(reserva.hora),
        'cantidad_personas': reserva.cantidad_personas,
        'numero_mesa': mesa.numero if mesa else None,
        'estado': reserva.estado,
        'notas': reserva.notas,
        'origen': reserva.origen,
        'espera_hasta': limite_de_espera(reserva).isoformat(timespec='minutes'),
        'cargada_por': _nombre(reserva.empleado),
        'fecha_hora_alta': fecha_iso(reserva.fecha_hora_alta),
        'cancelacion': cancelacion,
        'fecha_hora_resolucion': fecha_iso(reserva.fecha_hora_resolucion),
        'id_sesion': reserva.pedido_cabecera_id,
    }


def reserva_resumen(reserva):
    """Lo minimo que necesita el mozo para abrir la mesa por la reserva (viaja dentro de cada mesa)."""
    return {
        'id': reserva.id,
        'nombre': reserva.nombre,
        'apellido': reserva.apellido,
        'hora': texto_hora(reserva.hora),
        'turno': reserva.turno.nombre,
        'cantidad_personas': reserva.cantidad_personas,
        'notas': reserva.notas,
    }
