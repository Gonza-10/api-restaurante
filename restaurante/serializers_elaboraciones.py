"""Entrada de elaboraciones, producciones y configuracion del stock (hito 6)."""
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .elaboraciones import dependencias
from .models import Insumo, Receta
from .stock_calculos import MAX_DIAS_AVISO, MIN_DIAS_AVISO, es_entera, hay_ciclo

_MENSAJES_DECIMAL = {
    'required': 'Campo obligatorio.', 'invalid': 'Debe ser un numero.', 'min_value': 'Debe ser mayor que cero.',
    'max_decimal_places': 'Maximo 3 decimales.', 'max_digits': 'Numero demasiado grande.',
    'max_whole_digits': 'Numero demasiado grande.',
}


class IngredienteElaboracionSerializer(serializers.Serializer):
    insumo = serializers.PrimaryKeyRelatedField(
        queryset=Insumo.objects.filter(activo=True),
        error_messages={'does_not_exist': 'No existe un insumo activo con ese id.', 'required': 'Campo obligatorio.',
                        'incorrect_type': 'Debe ser el id del insumo.'},
    )
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal('0.001'), error_messages=_MENSAJES_DECIMAL
    )

    def validate(self, datos):
        if datos['insumo'].tipo_medida == 'Unidad' and not es_entera(datos['cantidad']):
            raise serializers.ValidationError({'cantidad': 'Este insumo se mide en unidades: la cantidad debe ser entera.'})
        return datos


class ElaboracionEntradaSerializer(serializers.Serializer):
    """POST /elaboraciones y PUT /elaboraciones/<id>. Una elaboracion cocina UN insumo propio (`insumo`) a partir de
    otros (`ingredientes`, por UNA tanda, en unidad base). `rinde` es cuanto sale de una tanda, en la unidad base del
    insumo producido; `dias_vencimiento` (opcional) es la vida util del lote producido. En el PUT, `ingredientes` reemplaza
    la lista completa y `insumo` no se puede cambiar. `nombre` es opcional: por defecto 'Elaboracion de <insumo>'."""
    insumo = serializers.PrimaryKeyRelatedField(
        queryset=Insumo.objects.filter(activo=True),
        error_messages={'does_not_exist': 'No existe un insumo activo con ese id.', 'required': 'Campo obligatorio.',
                        'incorrect_type': 'Debe ser el id del insumo.'},
    )
    nombre = serializers.CharField(max_length=100, required=False, allow_blank=True, trim_whitespace=True)
    descripcion = serializers.CharField(max_length=300, required=False, allow_null=True, allow_blank=True)
    rinde = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal('0.001'), error_messages=_MENSAJES_DECIMAL
    )
    dias_vencimiento = serializers.IntegerField(min_value=1, max_value=3650, required=False, allow_null=True)
    ingredientes = IngredienteElaboracionSerializer(many=True, error_messages={'required': 'Campo obligatorio.'})

    def validate_ingredientes(self, valor):
        if not valor:
            raise serializers.ValidationError('La elaboracion necesita al menos un ingrediente.')
        ids = [i['insumo'].id for i in valor]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Un insumo no puede repetirse en la misma elaboracion.')
        return valor

    def validate(self, datos):
        producido = datos['insumo']
        if self.instance is not None and self.instance.insumo_producido_id != producido.id:
            raise serializers.ValidationError({'insumo': 'El insumo producido no se puede cambiar: crear otra elaboracion.'})
        if self.instance is None and Receta.objects.filter(insumo_producido_id=producido.id).exists():
            raise serializers.ValidationError({'insumo': 'Ese insumo ya tiene una elaboracion. Editarla con PUT.'})
        if producido.tipo_medida == 'Unidad' and not es_entera(datos['rinde']):
            raise serializers.ValidationError({'rinde': 'El insumo se cuenta en unidades: lo que rinde debe ser entero.'})
        ids = [i['insumo'].id for i in datos['ingredientes']]
        if producido.id in ids:
            raise serializers.ValidationError({'ingredientes': f'{producido.nombre} no puede ser ingrediente de si mismo.'})
        excluir = self.instance.id if self.instance is not None else None
        if hay_ciclo(dependencias(excluir), producido.id, ids):
            raise serializers.ValidationError({'ingredientes': (
                f'Esos ingredientes forman un ciclo: alguno se elabora, directa o indirectamente, con {producido.nombre}.'
            )})
        nombre = (datos.get('nombre') or '').strip() or f'Elaboracion de {producido.nombre}'
        existentes = Receta.objects.filter(nombre__iexact=nombre)
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise serializers.ValidationError({'nombre': 'Ya existe una receta con ese nombre.'})
        datos['nombre'] = nombre
        return datos


class ProduccionEntradaSerializer(serializers.Serializer):
    """POST /producciones: Cocina registra que elaboro `tandas` tandas (1 por defecto) de una elaboracion. Descuenta
    los ingredientes por FEFO y da de alta el lote producido. `fecha_vencimiento` (opcional) reemplaza a la que sale de
    los `dias_vencimiento` de la elaboracion."""
    elaboracion = serializers.PrimaryKeyRelatedField(
        queryset=Receta.objects.filter(insumo_producido__isnull=False).select_related('insumo_producido'),
        error_messages={'does_not_exist': 'No existe una elaboracion con ese id.', 'required': 'Campo obligatorio.',
                        'incorrect_type': 'Debe ser el id de la elaboracion.'},
    )
    tandas = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal('0.001'), required=False, default=Decimal('1'),
        error_messages=_MENSAJES_DECIMAL,
    )
    nota = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True)

    def validate_fecha_vencimiento(self, valor):
        if valor is not None and valor < timezone.localdate():
            raise serializers.ValidationError('Esa fecha ya paso: el lote naceria vencido.')
        return valor

    def validate(self, datos):
        datos['nota'] = (datos.get('nota') or '').strip() or None
        return datos


class ConfiguracionStockSerializer(serializers.Serializer):
    """PUT /configuracion/stock. Dias de anticipacion con que se avisa que un lote esta por vencer."""
    dias_aviso_vencimiento = serializers.IntegerField(
        min_value=MIN_DIAS_AVISO, max_value=MAX_DIAS_AVISO,
        error_messages={'required': 'Campo obligatorio.', 'invalid': 'Debe ser un numero entero.',
                        'min_value': f'Debe ser {MIN_DIAS_AVISO} o mayor.', 'max_value': f'Maximo {MAX_DIAS_AVISO} dias.'},
    )
