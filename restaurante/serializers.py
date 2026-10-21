import random
import re
from decimal import Decimal

from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Producto, Mesa, Categoria, Empleado, Rol, PedidoCabecera, PedidoDetalle


def fecha_iso(valor):
    """Fecha y hora en ISO 8601 con zona horaria (la del proyecto), igual que los DateTimeField de DRF."""
    return serializers.DateTimeField().to_representation(valor) if valor else None


# ==================== MENÚ ====================

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'


class ProductoSerializer(serializers.ModelSerializer):
    precio = serializers.DecimalField(source='precio_actual', max_digits=10, decimal_places=2)
    vegetariano = serializers.BooleanField(source='es_vegetariano', required=False, default=False)
    sin_tacc = serializers.BooleanField(source='apto_celiaco', required=False, default=False)
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)

    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'precio', 'categoria', 'vegetariano', 'sin_tacc', 'categoria_nombre', 'activo', 'descripcion', 'imagen_url',
                  'tiempo_estimado', 'porciones']
        extra_kwargs = {
            'descripcion': {'required': False, 'allow_null': True, 'allow_blank': True},
            'imagen_url': {'required': False, 'allow_null': True, 'allow_blank': True},
            'tiempo_estimado': {'required': False, 'allow_null': True, 'min_value': 1},
            'porciones': {'required': False, 'allow_null': True, 'min_value': 1},
        }

    def validate_descripcion(self, value):
        value = (value or '').strip()
        return value or None

    def validate_imagen_url(self, value):
        # Solo se aceptan: un link externo https:// o una imagen ya subida a este servidor
        value = (value or '').strip()
        if not value:
            return None
        if len(value) > 500:
            raise serializers.ValidationError('El link es demasiado largo (maximo 500 caracteres).')
        if re.search(r'\s', value):
            raise serializers.ValidationError('El link no puede contener espacios.')
        if value.startswith('https://') and len(value) > len('https://'):
            return value
        if re.fullmatch(r'/media/productos/[0-9a-f]{32}\.(jpg|png|webp)', value):
            return value
        raise serializers.ValidationError(
            'La imagen debe ser un link que empiece con https:// o una imagen subida con POST /productos/{id}/imagen.'
        )

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor a 0.')
        return value


# ==================== MESAS ====================

class MesaSerializer(serializers.ModelSerializer):
    # el número es el identificador visible para mozo y cliente: no puede repetirse
    numero = serializers.IntegerField(
        validators=[UniqueValidator(
            queryset=Mesa.objects.all(),
            message='Ya existe una mesa con ese número.'
        )]
    )

    # datos de la sesion abierta de la mesa (vacios si esta libre); MesaViewSet los precarga en 'sesiones_abiertas'
    id_sesion = serializers.SerializerMethodField()
    mozo_nombre = serializers.SerializerMethodField()
    fecha_hora_inicio = serializers.SerializerMethodField()
    solicita_cuenta = serializers.SerializerMethodField()

    class Meta:
        model = Mesa
        fields = '__all__'

    def _sesion_abierta(self, obj):
        abiertas = getattr(obj, 'sesiones_abiertas', None)
        return abiertas[0] if abiertas else None

    def get_id_sesion(self, obj):
        sesion = self._sesion_abierta(obj)
        return sesion.id if sesion else None

    def get_mozo_nombre(self, obj):
        sesion = self._sesion_abierta(obj)
        return f'{sesion.empleado.nombre} {sesion.empleado.apellido}' if sesion else None

    def get_fecha_hora_inicio(self, obj):
        sesion = self._sesion_abierta(obj)
        return fecha_iso(sesion.fecha_hora_apertura) if sesion else None

    def get_solicita_cuenta(self, obj):
        sesion = self._sesion_abierta(obj)
        return bool(sesion and sesion.fecha_hora_solicita_cuenta)

    def validate_numero(self, value):
        if value <= 0:
            raise serializers.ValidationError('El número de mesa debe ser mayor a 0.')
        return value

    def validate_capacidad_maxima(self, value):
        if value <= 0:
            raise serializers.ValidationError('La capacidad debe ser mayor a 0.')
        return value

    def validate(self, data):
        # una mesa ocupada no se puede dar de baja (tampoco vía PATCH)
        if self.instance is not None and data.get('activa') is False and self.instance.estado:
            raise serializers.ValidationError(
                {'activa': 'No se puede dar de baja una mesa ocupada. Cerrá primero su sesión.'}
            )
        return data


# ==================== IDENTIDAD Y ACCESO ====================

class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id', 'nombre']


class EmpleadoSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(
        validators=[UniqueValidator(
            queryset=Empleado.objects.all(),
            message='Ese nombre de usuario ya está en uso.'
        )]
    )
    # el front envia "contrasena"; "contrasena_hash" se sigue aceptando por compatibilidad (coleccion de Postman)
    contrasena = serializers.CharField(write_only=True, required=False)
    contrasena_hash = serializers.CharField(write_only=True, required=False)  # nunca se devuelve en un GET
    fecha_ingreso = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Empleado
        fields = '__all__'

    def validate(self, data):
        clave = data.pop('contrasena', None)
        if clave is not None:
            data['contrasena_hash'] = clave
        if self.instance is None and not data.get('contrasena_hash'):
            raise serializers.ValidationError({'contrasena': 'La contraseña es obligatoria.'})
        return data

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
    comanda = serializers.PrimaryKeyRelatedField(read_only=True)

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
    numero_mesa = serializers.IntegerField(source='mesa.numero', read_only=True)
    mozo_nombre = serializers.SerializerMethodField()
    fecha_hora_inicio = serializers.DateTimeField(source='fecha_hora_apertura', read_only=True)
    fecha_hora_solicita_cuenta = serializers.DateTimeField(read_only=True)
    solicita_cuenta = serializers.SerializerMethodField()
    detalles = PedidoDetalleSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = PedidoCabecera
        fields = '__all__'

    def get_total(self, obj):
        return sum((detalle.sub_total for detalle in obj.detalles.all()), Decimal('0.00'))

    def get_mozo_nombre(self, obj):
        return f'{obj.empleado.nombre} {obj.empleado.apellido}'

    def get_solicita_cuenta(self, obj):
        return obj.estado == 'Abierto' and obj.fecha_hora_solicita_cuenta is not None

    def validate_cantidad_comensales(self, value):
        if value <= 0:
            raise serializers.ValidationError('Debe haber al menos un comensal.')
        return value

    def validate(self, data):
        if self.instance is None:  # esta regla aplica solo al abrir un pedido nuevo
            mesa = data.get('mesa')
            if mesa and not mesa.activa:
                raise serializers.ValidationError({'mesa': 'Esta mesa está dada de baja.'})
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

class SesionAbrirSerializer(serializers.Serializer):
    """Lo que manda el mozo al sentar clientes en una mesa."""
    numero_mesa = serializers.IntegerField(
        min_value=1,
        error_messages={'required': 'Campo obligatorio.', 'invalid': 'Debe ser un numero entero.', 'min_value': 'Debe ser mayor a 0.'}
    )
    cantidad_comensales = serializers.IntegerField(
        min_value=1,
        error_messages={'required': 'Campo obligatorio.', 'invalid': 'Debe ser un numero entero.', 'min_value': 'Debe haber al menos un comensal.'}
    )


class ItemComandaSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # asumido: Producto.Id
    nombre = serializers.CharField(required=False)  # se recibe, se ignora
    precio = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)  # se recibe, se ignora


class ComandaEntradaSerializer(serializers.Serializer):
    id_comanda_uuid = serializers.UUIDField()
    mesa_id = serializers.IntegerField()  # es el Numero de Mesa (D8)
    pin = serializers.RegexField(
        r'^\d{4}$',
        error_messages={'required': 'El PIN es obligatorio.', 'invalid': 'El PIN debe tener 4 digitos.', 'blank': 'El PIN es obligatorio.'}
    )
    items = ItemComandaSerializer(many=True)
    timestamp = serializers.DateTimeField(required=False)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('La comanda debe tener al menos un producto.')
        return value

class ItemCocinaSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    precio = serializers.DecimalField(max_digits=10, decimal_places=2)
    cantidad = serializers.IntegerField()


class ComandaCocinaSerializer(serializers.Serializer):
    id_comanda_uuid = serializers.UUIDField()
    mesa_id = serializers.CharField()
    items = ItemCocinaSerializer(many=True)
    estado = serializers.CharField()
    timestamp = serializers.DateTimeField()


class AccesoClienteSerializer(serializers.Serializer):
    """Lo que manda el cliente en los endpoints sin login: la mesa y el PIN que le dio el mozo."""
    numero_mesa = serializers.IntegerField(
        min_value=1,
        error_messages={'required': 'Campo obligatorio.', 'invalid': 'Debe ser un numero entero.', 'min_value': 'Debe ser mayor a 0.'}
    )
    pin = serializers.RegexField(
        r'^\d{4}$',
        error_messages={'required': 'El PIN es obligatorio.', 'invalid': 'El PIN debe tener 4 digitos.', 'blank': 'El PIN es obligatorio.'}
    )


class ItemHistorialSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    precio = serializers.DecimalField(max_digits=10, decimal_places=2)
    cantidad = serializers.IntegerField()
    sub_total = serializers.DecimalField(max_digits=10, decimal_places=2)


class ComandaHistorialSerializer(serializers.Serializer):
    id_comanda_uuid = serializers.UUIDField()
    estado = serializers.CharField()
    timestamp = serializers.DateTimeField()
    items = ItemHistorialSerializer(many=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class HistorialMesaSerializer(serializers.Serializer):
    numero_mesa = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    comandas = ComandaHistorialSerializer(many=True)