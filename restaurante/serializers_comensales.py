"""Entradas de los endpoints de comensales y seguridad de la mesa."""
from rest_framework import serializers

from .serializers import AccesoClienteSerializer


class IngresoComensalSerializer(AccesoClienteSerializer):
    """El dispositivo se presenta: mesa, PIN y el nombre que va a usar en la cuenta."""
    nombre = serializers.CharField(
        max_length=200, trim_whitespace=True,
        error_messages={'required': 'Ingresá tu nombre.', 'blank': 'Ingresá tu nombre.'}
    )


class OkComensalSerializer(AccesoClienteSerializer):
    """"Ya pedi todo": el OK de la primera ronda (ok=false lo retira para seguir pidiendo)."""
    id_comensal = serializers.IntegerField(min_value=1, error_messages={'required': 'Campo obligatorio.'})
    ok = serializers.BooleanField(required=False, default=True)


class RegenerarPinClienteSerializer(AccesoClienteSerializer):
    """Un comensal pide el PIN nuevo y marca quienes se fueron (`retirados`: ids de comensal; vacio = nadie, no se cancela nada)."""
    id_comensal = serializers.IntegerField(required=False, min_value=1)
    retirados = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list, max_length=50)


class RegenerarPinMozoSerializer(serializers.Serializer):
    retirados = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list, max_length=50)


class CancelarComandaSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=150, trim_whitespace=True)
