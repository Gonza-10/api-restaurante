"""Serializers de turnos, jornadas y especiales."""
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .jornadas import cierre_previsto, duracion_segundos, sugerir_cierre
from .models import Turno, Jornada, Especial, DiaEspecial, PedidoCabecera
from .serializers import fecha_iso

FORMATOS_HORA = ['%H:%M', '%H:%M:%S']
DIAS_SEMANA = {1: 'Lunes', 2: 'Martes', 3: 'Miercoles', 4: 'Jueves', 5: 'Viernes', 6: 'Sabado', 7: 'Domingo'}


# ==================== TURNOS (horarios de atencion) ====================

class TurnoSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(
        max_length=30,
        validators=[UniqueValidator(queryset=Turno.objects.all(), message='Ya existe un turno con ese nombre.')]
    )
    hora_apertura = serializers.TimeField(format='%H:%M', input_formats=FORMATOS_HORA)
    hora_cierre = serializers.TimeField(format='%H:%M', input_formats=FORMATOS_HORA)

    class Meta:
        model = Turno
        fields = ['id', 'nombre', 'hora_apertura', 'hora_cierre', 'activo']

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El nombre no puede estar vacio.')
        return value

    def validate(self, data):
        apertura = data.get('hora_apertura', self.instance.hora_apertura if self.instance else None)
        cierre = data.get('hora_cierre', self.instance.hora_cierre if self.instance else None)
        if apertura is not None and apertura == cierre:
            raise serializers.ValidationError({'hora_cierre': 'La hora de cierre no puede ser igual a la de apertura.'})
        return data


# ==================== JORNADAS ====================

class JornadaAbrirSerializer(serializers.Serializer):
    turno = serializers.PrimaryKeyRelatedField(queryset=Turno.objects.filter(activo=True), required=False, allow_null=True)


class JornadaSerializer(serializers.ModelSerializer):
    turno_nombre = serializers.CharField(source='turno.nombre', read_only=True)
    apertura_por = serializers.SerializerMethodField()
    cierre_por = serializers.SerializerMethodField()
    duracion_segundos = serializers.SerializerMethodField()
    hora_cierre_prevista = serializers.SerializerMethodField()
    sugerir_cierre = serializers.SerializerMethodField()
    mesas_abiertas = serializers.SerializerMethodField()

    class Meta:
        model = Jornada
        fields = [
            'id', 'turno', 'turno_nombre', 'fecha', 'estado',
            'fecha_hora_apertura', 'apertura_por', 'fecha_hora_cierre', 'cierre_por',
            'duracion_segundos', 'hora_cierre_prevista', 'sugerir_cierre', 'mesas_abiertas',
        ]
        read_only_fields = fields

    def get_apertura_por(self, obj):
        return f'{obj.empleado_apertura.nombre} {obj.empleado_apertura.apellido}'

    def get_cierre_por(self, obj):
        return f'{obj.empleado_cierre.nombre} {obj.empleado_cierre.apellido}' if obj.empleado_cierre else None

    def get_duracion_segundos(self, obj):
        return duracion_segundos(obj)

    def get_hora_cierre_prevista(self, obj):
        return fecha_iso(cierre_previsto(obj)) if obj.estado == 'Abierta' else None

    def get_sugerir_cierre(self, obj):
        return sugerir_cierre(obj)

    def get_mesas_abiertas(self, obj):
        if obj.estado != 'Abierta':
            return None
        return PedidoCabecera.objects.filter(jornada=obj, estado='Abierto').count()


# ==================== ESPECIALES ====================

class EspecialSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    precio_normal = serializers.DecimalField(source='producto.precio_actual', max_digits=10, decimal_places=2, read_only=True)
    turno_nombre = serializers.SerializerMethodField()
    # solo para especiales de una fecha: True = ese dia valen solo los de la fecha; False = se suman a los semanales
    reemplaza_semanales = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Especial
        fields = [
            'id', 'producto', 'producto_nombre', 'precio_normal', 'precio_especial',
            'turno', 'turno_nombre', 'dia_semana', 'fecha', 'reemplaza_semanales',
        ]
        extra_kwargs = {
            'turno': {'required': False, 'allow_null': True},
            'dia_semana': {'required': False, 'allow_null': True, 'min_value': 1, 'max_value': 7},
            'fecha': {'required': False, 'allow_null': True},
        }

    def get_turno_nombre(self, obj):
        return obj.turno.nombre if obj.turno else 'Todo el dia'

    def validate_precio_especial(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio especial debe ser mayor a 0.')
        return value

    def validate(self, data):
        actual = self.instance
        producto = data.get('producto', actual.producto if actual else None)
        precio = data.get('precio_especial', actual.precio_especial if actual else None)
        turno = data['turno'] if 'turno' in data else (actual.turno if actual else None)
        dia_semana = data['dia_semana'] if 'dia_semana' in data else (actual.dia_semana if actual else None)
        fecha = data['fecha'] if 'fecha' in data else (actual.fecha if actual else None)

        if (dia_semana is None) == (fecha is None):
            raise serializers.ValidationError(
                {'dia_semana': 'Indicar dia_semana (1=lunes ... 7=domingo) para una regla semanal, o fecha para una fecha puntual, pero no ambos.'}
            )
        if 'reemplaza_semanales' in data and fecha is None:
            raise serializers.ValidationError({'reemplaza_semanales': 'Solo aplica a especiales de una fecha puntual.'})
        if producto is not None and not producto.activo:
            raise serializers.ValidationError({'producto': 'El producto esta dado de baja.'})
        if producto is not None and precio is not None and precio >= producto.precio_actual:
            raise serializers.ValidationError(
                {'precio_especial': f'Debe ser menor al precio normal ({producto.precio_actual}).'}
            )
        if turno is not None and not turno.activo:
            raise serializers.ValidationError({'turno': 'El turno esta dado de baja.'})

        # el mismo plato no puede repetirse en la misma regla con turnos que se superponen
        repetidos = Especial.objects.filter(producto=producto, dia_semana=dia_semana, fecha=fecha)
        if actual is not None:
            repetidos = repetidos.exclude(pk=actual.pk)
        if turno is not None:
            repetidos = repetidos.filter(Q(turno__isnull=True) | Q(turno=turno))
        if repetidos.exists():
            raise serializers.ValidationError('Ese plato ya es especial en ese dia y en un turno que se superpone.')
        return data

    def _aplicar_modo_de_la_fecha(self, especial, reemplaza):
        if especial.fecha is None:
            return
        config, creada = DiaEspecial.objects.get_or_create(fecha=especial.fecha, defaults={'reemplaza': bool(reemplaza)})
        if not creada and reemplaza is not None and config.reemplaza != reemplaza:
            config.reemplaza = reemplaza
            config.save(update_fields=['reemplaza'])

    def create(self, validated_data):
        reemplaza = validated_data.pop('reemplaza_semanales', None)
        with transaction.atomic():
            especial = super().create(validated_data)
            self._aplicar_modo_de_la_fecha(especial, reemplaza)
        return especial

    def update(self, instance, validated_data):
        reemplaza = validated_data.pop('reemplaza_semanales', None)
        with transaction.atomic():
            especial = super().update(instance, validated_data)
            self._aplicar_modo_de_la_fecha(especial, reemplaza)
        return especial
