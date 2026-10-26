"""Serializadores de entrada de las recetas (hito 2). La salida la arma recetas.armar_receta."""
from decimal import Decimal

from rest_framework import serializers

from .models import Insumo, Receta
from .stock_calculos import es_entera


class IngredienteEntradaSerializer(serializers.Serializer):
    insumo = serializers.PrimaryKeyRelatedField(
        queryset=Insumo.objects.filter(activo=True),
        error_messages={'does_not_exist': 'No existe un insumo activo con ese id.', 'required': 'Campo obligatorio.',
                        'incorrect_type': 'Debe ser el id del insumo.'},
    )
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal('0.001'),
        error_messages={'required': 'Campo obligatorio.', 'invalid': 'Debe ser un numero.',
                        'min_value': 'Debe ser mayor que cero.', 'max_decimal_places': 'Maximo 3 decimales.',
                        'max_digits': 'Numero demasiado grande.', 'max_whole_digits': 'Numero demasiado grande.'},
    )

    def validate(self, datos):
        # las unidades no se parten: no existe "medio huevo" en una receta
        if datos['insumo'].tipo_medida == 'Unidad' and not es_entera(datos['cantidad']):
            raise serializers.ValidationError({'cantidad': 'Este insumo se mide en unidades: la cantidad debe ser entera.'})
        return datos


class RecetaEntradaSerializer(serializers.Serializer):
    """POST /recetas y PUT /recetas/<id>. En el PUT, `ingredientes` reemplaza la lista completa.
    Las cantidades son por UNA unidad vendida y van en unidad base (g, ml o u)."""
    nombre = serializers.CharField(
        max_length=100, trim_whitespace=True,
        error_messages={'required': 'Campo obligatorio.', 'blank': 'Campo obligatorio.',
                        'max_length': 'Maximo 100 caracteres.'},
    )
    descripcion = serializers.CharField(max_length=300, required=False, allow_null=True, allow_blank=True)
    ingredientes = IngredienteEntradaSerializer(many=True, error_messages={'required': 'Campo obligatorio.'})

    def validate_nombre(self, valor):
        existentes = Receta.objects.filter(nombre__iexact=valor)
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise serializers.ValidationError('Ya existe una receta con ese nombre.')
        return valor

    def validate_ingredientes(self, valor):
        if not valor:
            raise serializers.ValidationError('La receta necesita al menos un ingrediente.')
        ids = [i['insumo'].id for i in valor]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Un insumo no puede repetirse en la misma receta.')
        return valor
