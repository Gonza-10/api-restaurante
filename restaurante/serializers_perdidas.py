"""Entrada de las perdidas (hito 4)."""
from decimal import Decimal

from rest_framework import serializers

from .models import Insumo, Producto
from .stock_calculos import CODIGOS_MOTIVO, MOTIVO_OTRO, es_entera

TIPOS_PERDIDA = ('insumo', 'plato')


class PerdidaEntradaSerializer(serializers.Serializer):
    """POST /perdidas. Dos formas:
      {"tipo": "insumo", "insumo": id, "cantidad": 250, "motivo": "rotura_derrame"}   cantidad en unidad base (g, ml, u)
      {"tipo": "plato", "producto": id, "cantidad": 2, "motivo": "error_cocina"}       cantidad en platos enteros
    `nota` es opcional, salvo con el motivo 'otro' (ahi explica que paso)."""
    tipo = serializers.ChoiceField(
        choices=TIPOS_PERDIDA, error_messages={'invalid_choice': "Valores validos: 'insumo' o 'plato'."}
    )
    insumo = serializers.PrimaryKeyRelatedField(queryset=Insumo.objects.filter(activo=True), required=False)
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all(), required=False)
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
    motivo = serializers.ChoiceField(
        choices=CODIGOS_MOTIVO,
        error_messages={'invalid_choice': f"Motivo invalido. Valores validos: {', '.join(CODIGOS_MOTIVO)}."},
    )
    nota = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)

    def validate(self, datos):
        nota = (datos.get('nota') or '').strip() or None
        datos['nota'] = nota
        if datos['motivo'] == MOTIVO_OTRO and nota is None:
            raise serializers.ValidationError({'nota': "Con el motivo 'otro' hay que explicar que paso."})

        if datos['tipo'] == 'insumo':
            if 'insumo' not in datos:
                raise serializers.ValidationError({'insumo': 'Indicar el insumo que se perdio.'})
            if 'producto' in datos:
                raise serializers.ValidationError({'producto': "Una perdida de insumo no lleva 'producto'."})
            if datos['insumo'].tipo_medida == 'Unidad' and not es_entera(datos['cantidad']):
                raise serializers.ValidationError({'cantidad': 'Este insumo se cuenta en unidades enteras.'})
        else:
            if 'producto' not in datos:
                raise serializers.ValidationError({'producto': 'Indicar el plato que se perdio.'})
            if 'insumo' in datos:
                raise serializers.ValidationError({'insumo': "Una perdida de plato no lleva 'insumo'."})
            if not es_entera(datos['cantidad']):
                raise serializers.ValidationError({'cantidad': 'Los platos se pierden de a unidades enteras.'})
            if datos['producto'].receta_id is None:
                raise serializers.ValidationError({
                    'producto': 'El plato no tiene receta: no hay insumos que descontar. Pedirle a un Admin o Gerente que se la asigne.'
                })
        return datos


class MotivoBajaSerializer(serializers.Serializer):
    """POST /lotes/<id>/baja. `motivo` es el texto que explica la baja; `motivo_codigo` (opcional) es el de la lista
    cerrada. Sin codigo: 'vencimiento' si el lote ya vencio, 'otro' en los demas casos."""
    motivo = serializers.CharField(max_length=100)
    motivo_codigo = serializers.ChoiceField(
        choices=CODIGOS_MOTIVO, required=False,
        error_messages={'invalid_choice': f"Motivo invalido. Valores validos: {', '.join(CODIGOS_MOTIVO)}."},
    )

    def validate_motivo(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El motivo no puede estar vacio.')
        return value
