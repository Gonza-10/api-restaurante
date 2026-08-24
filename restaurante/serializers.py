from rest_framework import serializers
from .models import Producto, Mesa, Mozo

class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = '__all__'

class MesaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mesa
        fields = '__all__'

class MozoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mozo
        fields = '__all__'