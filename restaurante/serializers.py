import random
import re
from decimal import Decimal

from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Producto, Mesa, Categoria, Empleado, Rol, PedidoCabecera, PedidoDetalle
from .comensales_calculos import modalidad_valida
from .especiales import precios_especiales_vigentes
from .modificadores import quitables_de_productos
from .extras import extras_de_productos


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
    # precio especial vigente (de la jornada abierta); null si el plato no es especial ahora
    precio_especial = serializers.SerializerMethodField()
    es_especial_hoy = serializers.SerializerMethodField()
    # disponibilidad (solo lectura): se cambia con POST /productos/{id}/agotar y /reactivar, o la calcula el stock
    disponible = serializers.BooleanField(read_only=True)
    agotado_manual = serializers.BooleanField(read_only=True)
    agotado_desde = serializers.SerializerMethodField()
    agotado_por = serializers.SerializerMethodField()
    visible = serializers.BooleanField(source='visible_cliente', read_only=True)
    # ingredientes que el cliente puede pedir quitar de este plato (hito 5): solo id y nombre, el resto de la receta es interno
    quitables = serializers.SerializerMethodField()
    # extras que se le pueden sumar al plato con recargo (cobros, hito 5): id, nombre, precio y maximo por unidad. El menu del
    # cliente solo trae los activos y con stock; el listado de gestion (incluir_inactivos) trae todos con sus datos internos
    extras = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'precio', 'categoria', 'vegetariano', 'sin_tacc', 'categoria_nombre', 'activo', 'descripcion', 'imagen_url',
                  'tiempo_estimado', 'porciones', 'precio_especial', 'es_especial_hoy',
                  'disponible', 'agotado_manual', 'agotado_desde', 'agotado_por', 'visible', 'quitables', 'extras']
        extra_kwargs = {
            'descripcion': {'required': False, 'allow_null': True, 'allow_blank': True},
            'imagen_url': {'required': False, 'allow_null': True, 'allow_blank': True},
            'tiempo_estimado': {'required': False, 'allow_null': True, 'min_value': 1},
            'porciones': {'required': False, 'allow_null': True, 'min_value': 1},
        }

    def _precio_especial_vigente(self, obj):
        precios = self.context.get('precios_especiales')
        if precios is None:  # fuera del listado (por ejemplo, tras subir una imagen)
            precios = precios_especiales_vigentes()
        precio = precios.get(obj.id)
        # un especial que no baja el precio no se muestra (el precio normal pudo cambiar despues)
        return precio if precio is not None and precio < obj.precio_actual else None

    def _es_personal(self):
        # el menu es publico: quien agoto un plato (nombre del empleado) solo lo ve el personal logueado
        solicitud = self.context.get('request')
        return bool(getattr(getattr(solicitud, 'user', None), 'is_authenticated', False))

    def get_quitables(self, obj):
        por_producto = self.context.get('quitables_por_producto')
        if por_producto is None:  # fuera del listado (por ejemplo, tras crear o editar un producto)
            por_producto = quitables_de_productos([obj.id])
        quitables = por_producto.get(obj.id, {})
        return [{'id': i, 'nombre': nombre} for i, nombre in sorted(quitables.items(), key=lambda par: par[1].lower())]

    def get_extras(self, obj):
        por_producto = self.context.get('extras_por_producto')
        if por_producto is None:  # fuera del listado (por ejemplo, tras crear o editar un producto)
            por_producto = extras_de_productos([obj.id])
        return por_producto.get(obj.id, [])

    def get_agotado_desde(self, obj):
        return fecha_iso(obj.fecha_hora_agotado) if obj.agotado_manual and self._es_personal() else None

    def get_agotado_por(self, obj):
        if not obj.agotado_manual or obj.empleado_agotado is None or not self._es_personal():
            return None
        return f'{obj.empleado_agotado.nombre} {obj.empleado_agotado.apellido}'

    def get_precio_especial(self, obj):
        precio = self._precio_especial_vigente(obj)
        return f'{precio:.2f}' if precio is not None else None

    def get_es_especial_hoy(self, obj):
        return self._precio_especial_vigente(obj) is not None

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
    # con que medio dijo el cliente que quiere pagar (Efectivo / MercadoPago / Tarjeta) al pedir la cuenta; None si no lo dijo
    metodo_pago_solicitado = serializers.SerializerMethodField()
    # reserva que bloquea la mesa en la jornada abierta (la arma MesaViewSet en el contexto); None si no hay
    reserva = serializers.SerializerMethodField()
    # modalidad de la sesion abierta (Familiar / Grupal) y si la primera ronda ya salio a cocina; None si la mesa esta libre
    modalidad = serializers.SerializerMethodField()
    ronda_liberada = serializers.SerializerMethodField()
    # aviso urgente para el mozo: alguien pidio un PIN nuevo y el mozo todavia no lo vio. None si no hay aviso pendiente.
    aviso_pin = serializers.SerializerMethodField()

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

    def get_metodo_pago_solicitado(self, obj):
        sesion = self._sesion_abierta(obj)
        return sesion.metodo_pago_solicitado if sesion and sesion.fecha_hora_solicita_cuenta else None

    def get_reserva(self, obj):
        return self.context.get('reservas_por_mesa', {}).get(obj.id)

    def get_modalidad(self, obj):
        sesion = self._sesion_abierta(obj)
        return sesion.modalidad if sesion else None

    def get_ronda_liberada(self, obj):
        sesion = self._sesion_abierta(obj)
        return sesion.ronda_liberada if sesion else None

    def get_aviso_pin(self, obj):
        sesion = self._sesion_abierta(obj)
        if not sesion or not sesion.aviso_pin_pendiente:
            return None
        return {'solicitado_por': sesion.pin_regenerado_por, 'fecha_hora': fecha_iso(sesion.pin_regenerado_en)}

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
    jornada = serializers.PrimaryKeyRelatedField(read_only=True)
    mozo_nombre = serializers.SerializerMethodField()
    fecha_hora_inicio = serializers.DateTimeField(source='fecha_hora_apertura', read_only=True)
    fecha_hora_solicita_cuenta = serializers.DateTimeField(read_only=True)
    solicita_cuenta = serializers.SerializerMethodField()
    detalles = PedidoDetalleSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = PedidoCabecera
        exclude = ['pins_anteriores']   # los PIN viejos son solo para avisar "el PIN cambio" al dispositivo que todavia lo usa

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
    # Si la mesa tiene una reserva en la jornada, solo se abre indicando esa reserva (el mozo confirma que es la del cliente).
    reserva_id = serializers.IntegerField(
        required=False, min_value=1,
        error_messages={'invalid': 'Debe ser un numero entero.', 'min_value': 'Debe ser mayor a 0.'}
    )
    # Familiar (por defecto) o Grupal: la elige el mozo segun quienes se sientan.
    modalidad = serializers.CharField(required=False, default='Familiar')

    def validate_modalidad(self, value):
        modalidad = modalidad_valida(value)
        if modalidad is None:
            raise serializers.ValidationError("La modalidad debe ser 'Familiar' o 'Grupal'.")
        return modalidad


class ExtraComandaSerializer(serializers.Serializer):
    """Un extra pedido para UNA unidad del plato: id del extra (RecetaExtra) y cuantas unidades de extra."""
    id = serializers.IntegerField(min_value=1)
    cantidad = serializers.IntegerField(min_value=1, max_value=10, default=1)


class ItemComandaSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # asumido: Producto.Id
    nombre = serializers.CharField(required=False)  # se recibe, se ignora
    precio = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)  # se recibe, se ignora
    # ids de los insumos que se quitan de ESTA unidad ("sin cebolla"); solo valen los que la receta marca como quitables
    sin = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list, max_length=20,
        error_messages={'not_a_list': 'Debe ser una lista de ids de insumos.'},
    )

    # plato para compartir: nombres de quienes lo dividen (el total se reparte en partes iguales entre ellos). Se elige antes
    # de confirmar el pedido; los nombres pueden ser de comensales cargados o no.
    compartido = serializers.ListField(
        child=serializers.CharField(max_length=50, allow_blank=False, trim_whitespace=True), required=False, default=list,
        max_length=20, error_messages={'not_a_list': 'Debe ser una lista de nombres.'},
    )

    # extras que suma el cliente a ESTA unidad (cobros, hito 5): [{"id": id_extra, "cantidad": 2}]. Solo valen los que la
    # receta del plato ofrece y tienen stock; el recargo lo pone el servidor (nunca el cliente)
    extras = ExtraComandaSerializer(many=True, required=False, default=list)

    def validate_extras(self, value):
        ids = [e['id'] for e in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('No repitas el mismo extra: indica la cantidad.')
        if len(ids) > 10:
            raise serializers.ValidationError('Hasta 10 extras distintos por plato.')
        return sorted(value, key=lambda e: e['id'])   # mismo orden siempre: dos unidades iguales quedan en el mismo renglon

    def validate_sin(self, value):
        return sorted(set(value))  # sin repetidos y en orden: dos unidades iguales quedan en el mismo renglon

    def validate_compartido(self, value):
        vistos, limpios = set(), []
        for nombre in value:
            clave = nombre.strip().casefold()
            if clave and clave not in vistos:
                vistos.add(clave)
                limpios.append(nombre.strip())
        if len(limpios) == 1:
            raise serializers.ValidationError('Para compartir un plato hacen falta al menos dos personas.')
        return sorted(limpios, key=str.casefold)   # mismo orden siempre: dos unidades iguales quedan en el mismo renglon


class ComandaEntradaSerializer(serializers.Serializer):
    id_comanda_uuid = serializers.UUIDField()
    mesa_id = serializers.IntegerField()  # es el Numero de Mesa (D8)
    pin = serializers.RegexField(
        r'^\d{4}$',
        error_messages={'required': 'El PIN es obligatorio.', 'invalid': 'El PIN debe tener 4 digitos.', 'blank': 'El PIN es obligatorio.'}
    )
    items = ItemComandaSerializer(many=True)
    timestamp = serializers.DateTimeField(required=False)
    # version del menu que el cliente tenia al armar el pedido (header X-Catalogo-Version de GET /productos)
    version_menu = serializers.IntegerField(required=False, min_value=0)
    # quien pide (opcional): su nombre en la cuenta. Los platos 'compartido' se reparten aparte.
    comensal = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True, trim_whitespace=True)
    # perfil del comensal (POST /mesa/comensales): en una mesa Grupal es obligatorio y reemplaza al nombre suelto
    id_comensal = serializers.IntegerField(required=False, min_value=1)

    def validate_comensal(self, value):
        return (value or '').strip() or None

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('La comanda debe tener al menos un producto.')
        return value

class ItemCocinaSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    precio = serializers.DecimalField(max_digits=10, decimal_places=2)
    cantidad = serializers.IntegerField()
    # ingredientes que el cliente pidio quitar ("Cebolla"), ordenados; lista vacia si no quito ninguno
    sin = serializers.ListField(child=serializers.CharField(), required=False)
    # extras que sumo el cliente ("Cheddar", "Aderezo x2"), ordenados; lista vacia si no sumo ninguno
    extras = serializers.ListField(child=serializers.CharField(), required=False)


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
    sin = serializers.ListField(child=serializers.CharField(), required=False)  # ingredientes quitados
    # extras con recargo: [{"nombre": "Cheddar", "cantidad": 2, "precio": "500.00"}]; `precio` ya esta incluido en el del renglon
    extras = serializers.ListField(child=serializers.DictField(), required=False)


class ComandaHistorialSerializer(serializers.Serializer):
    id_comanda_uuid = serializers.UUIDField()
    estado = serializers.CharField()
    timestamp = serializers.DateTimeField()
    items = ItemHistorialSerializer(many=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    # solo en las comandas rechazadas por falta de insumos: texto para mostrar al cliente (null en el resto)
    mensaje = serializers.CharField(allow_null=True, required=False)
    # quien hizo el pedido (nombre del comensal; null si no se indico)
    comensal = serializers.CharField(allow_null=True, required=False)


class HistorialMesaSerializer(serializers.Serializer):
    numero_mesa = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    comandas = ComandaHistorialSerializer(many=True)