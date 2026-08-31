import random
from decimal import Decimal

from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Producto, Mesa, Categoria, Empleado, PedidoCabecera, PedidoDetalle


# ==================== MENÚ ====================

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'


class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = '__all__'

    def validate_precio_actual(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor a 0.')
        return value


# ==================== MESAS ====================

class MesaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mesa
        fields = '__all__'

    def validate_capacidad_maxima(self, value):
        if value <= 0:
            raise serializers.ValidationError('La capacidad debe ser mayor a 0.')
        return value


# ==================== IDENTIDAD Y ACCESO ====================

class EmpleadoSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(
        validators=[UniqueValidator(
            queryset=Empleado.objects.all(),
            message='Ese nombre de usuario ya está en uso.'
        )]
    )
    contrasena_hash = serializers.CharField(write_only=True)  # nunca se devuelve en un GET
    fecha_ingreso = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Empleado
        fields = '__all__'

    def create(self, validated_data):
        # nunca guardamos la contraseña tal cual la mandó el cliente
        validated_data['contrasena_hash'] = make_password(validated_data['contrasena_hash'])
        validated_data['fecha_ingreso'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'contrasena_hash' in validated_data:
            validated_data['contrasena_hash'] = make_password(validated_data['contrasena_hash'])
        return super().update(instance, validated_data)


# ==================== PEDIDOS ====================

class PedidoDetalleSerializer(serializers.ModelSerializer):
    precio_unitario = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    sub_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = PedidoDetalle
        fields = '__all__'

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad debe ser mayor a 0.')
        return value

    def validate(self, data):
        producto = data.get('producto') or getattr(self.instance, 'producto', None)
        if producto and not producto.activo:
            raise serializers.ValidationError(
                {'producto': 'Este producto no está disponible actualmente.'}
            )
        return data

    def create(self, validated_data):
        producto = validated_data['producto']
        cantidad = validated_data['cantidad']
        # snapshot del precio + cálculo del subtotal, el cliente nunca los manda
        validated_data['precio_unitario'] = producto.precio_actual
        validated_data['sub_total'] = producto.precio_actual * cantidad
        return super().create(validated_data)

    def update(self, instance, validated_data):
        producto = validated_data.get('producto', instance.producto)
        cantidad = validated_data.get('cantidad', instance.cantidad)
        validated_data['precio_unitario'] = producto.precio_actual
        validated_data['sub_total'] = producto.precio_actual * cantidad
        return super().update(instance, validated_data)


class PedidoCabeceraSerializer(serializers.ModelSerializer):
    codigo_pin = serializers.CharField(read_only=True)
    fecha_hora_apertura = serializers.DateTimeField(read_only=True)
    detalles = PedidoDetalleSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = PedidoCabecera
        fields = '__all__'

    def get_total(self, obj):
        return sum((detalle.sub_total for detalle in obj.detalles.all()), Decimal('0.00'))

    def validate_cantidad_comensales(self, value):
        if value <= 0:
            raise serializers.ValidationError('Debe haber al menos un comensal.')
        return value

    def validate(self, data):
        if self.instance is None:  # esta regla aplica solo al abrir un pedido nuevo
            mesa = data.get('mesa')
            if mesa and mesa.estado:
                raise serializers.ValidationError({'mesa': 'Esta mesa ya está ocupada.'})
        return data

    def create(self, validated_data):
        mesa = validated_data['mesa']
        validated_data['codigo_pin'] = str(random.randint(1000, 9999))
        validated_data['fecha_hora_apertura'] = timezone.now()
        validated_data['estado'] = 'Abierto'  # se ignora lo que mande el cliente acá
        pedido = super().create(validated_data)
        mesa.estado = True  # ocupar la mesa automáticamente al abrir el pedido
        mesa.save(update_fields=['estado'])
        return pedido

    def update(self, instance, validated_data):
        pedido = super().update(instance, validated_data)
        if pedido.fecha_hora_cierre and pedido.estado == 'Cerrado':
            mesa = pedido.mesa
            mesa.estado = False  # liberar la mesa al cerrar el pedido
            mesa.save(update_fields=['estado'])
        return pedido