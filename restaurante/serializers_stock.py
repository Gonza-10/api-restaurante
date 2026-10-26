"""Serializers del stock: proveedores, insumos, compras, lotes, movimientos, ajustes."""
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Compra, Insumo, LoteInsumo, MovimientoStock, Proveedor, StockInsumo
from .serializers import fecha_iso
from .stock import proveedores_por_insumo
from .stock_calculos import (
    SEMAFORO, TIPOS_MEDIDA, UNIDAD_BASE, costo_total_lote, cuantizar_cantidad, es_entera, texto_cantidad,
)

CANTIDAD = dict(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))


def _nombre_empleado(empleado):
    return f'{empleado.nombre} {empleado.apellido}' if empleado else None


def _limpiar_textos(data, campos):
    """Texto vacio o solo espacios = sin dato (NULL)."""
    for campo in campos:
        if campo in data and isinstance(data[campo], str):
            data[campo] = data[campo].strip() or None
    return data


# ==================== PROVEEDORES ====================

class ProveedorSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(
        max_length=100,
        validators=[UniqueValidator(queryset=Proveedor.objects.all(), message='Ya existe un proveedor con ese nombre.')]
    )
    email = serializers.EmailField(max_length=120, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Proveedor
        fields = ['id', 'nombre', 'contacto', 'telefono', 'email', 'direccion', 'notas', 'activo']
        extra_kwargs = {
            campo: {'required': False, 'allow_null': True, 'allow_blank': True}
            for campo in ('contacto', 'telefono', 'direccion', 'notas')
        }

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El nombre no puede estar vacio.')
        return value

    def validate(self, data):
        return _limpiar_textos(data, ('contacto', 'telefono', 'email', 'direccion', 'notas'))


# ==================== INSUMOS ====================

class InsumoSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(
        max_length=100,
        validators=[UniqueValidator(queryset=Insumo.objects.all(), message='Ya existe un insumo con ese nombre.')]
    )
    tipo_medida = serializers.ChoiceField(choices=TIPOS_MEDIDA)
    stock_objetivo = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0'), required=False)
    umbral_bajo_pct = serializers.IntegerField(min_value=1, max_value=100, required=False)
    umbral_critico_pct = serializers.IntegerField(min_value=0, max_value=99, required=False)
    unidad_base = serializers.SerializerMethodField()
    stock_actual = serializers.SerializerMethodField()
    porcentaje = serializers.SerializerMethodField()
    estado = serializers.SerializerMethodField()
    semaforo = serializers.SerializerMethodField()
    proveedores = serializers.SerializerMethodField()

    class Meta:
        model = Insumo
        fields = [
            'id', 'nombre', 'tipo_medida', 'unidad_base', 'stock_objetivo', 'umbral_bajo_pct', 'umbral_critico_pct',
            'activo', 'stock_actual', 'porcentaje', 'estado', 'semaforo', 'proveedores',
        ]

    # --- lectura: el stock y los proveedores llegan precalculados en el contexto (listados) o se buscan de a uno ---
    def _stock(self, obj):
        mapa = self.context.get('stock_por_insumo')
        if mapa is not None:
            return mapa.get(obj.id)
        return StockInsumo.objects.filter(pk=obj.id).first()

    def get_unidad_base(self, obj):
        return UNIDAD_BASE[obj.tipo_medida]

    def get_stock_actual(self, obj):
        fila = self._stock(obj)
        return str(fila.stock_actual) if fila else '0.000'

    def get_porcentaje(self, obj):
        fila = self._stock(obj)
        return str(fila.porcentaje) if fila and fila.porcentaje is not None else None

    def get_estado(self, obj):
        fila = self._stock(obj)
        return fila.estado if fila else 'Agotado'

    def get_semaforo(self, obj):
        return SEMAFORO[self.get_estado(obj)]

    def get_proveedores(self, obj):
        mapa = self.context.get('proveedores_por_insumo')
        if mapa is None:
            mapa = proveedores_por_insumo([obj.id])
        return mapa.get(obj.id, [])

    # --- escritura ---
    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El nombre no puede estar vacio.')
        return value

    def validate(self, data):
        actual = self.instance
        bajo = data.get('umbral_bajo_pct', actual.umbral_bajo_pct if actual else 50)
        critico = data.get('umbral_critico_pct', actual.umbral_critico_pct if actual else 20)
        if critico >= bajo:
            raise serializers.ValidationError(
                {'umbral_critico_pct': 'El umbral critico (rojo) tiene que ser menor que el umbral bajo (amarillo).'}
            )
        if actual and 'tipo_medida' in data and data['tipo_medida'] != actual.tipo_medida:
            if LoteInsumo.objects.filter(insumo=actual).exists():
                raise serializers.ValidationError(
                    {'tipo_medida': 'No se puede cambiar el tipo de medida: el insumo ya tiene lotes cargados.'}
                )
        return data


class ProveedorDeInsumoSerializer(serializers.Serializer):
    proveedor = serializers.PrimaryKeyRelatedField(queryset=Proveedor.objects.filter(activo=True))
    es_principal = serializers.BooleanField(required=False, default=False)


class AsignarProveedoresSerializer(serializers.Serializer):
    proveedores = ProveedorDeInsumoSerializer(many=True, allow_empty=True)

    def validate_proveedores(self, items):
        ids = [item['proveedor'].id for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Un proveedor no puede repetirse.')
        if sum(1 for item in items if item['es_principal']) > 1:
            raise serializers.ValidationError('Solo un proveedor puede ser el principal.')
        return items


# ==================== LOTES, COMPRAS Y MOVIMIENTOS ====================

class LoteSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    unidad_base = serializers.SerializerMethodField()
    fecha_ingreso = serializers.SerializerMethodField()
    dias_para_vencer = serializers.SerializerMethodField()
    costo_total = serializers.SerializerMethodField()

    class Meta:
        model = LoteInsumo
        fields = [
            'id', 'insumo', 'insumo_nombre', 'unidad_base', 'compra', 'origen', 'fecha_ingreso', 'fecha_vencimiento',
            'dias_para_vencer', 'tamano_presentacion', 'cantidad_presentaciones', 'cantidad_inicial', 'cantidad_actual',
            'costo_unitario', 'costo_total', 'estado',
        ]
        read_only_fields = fields

    def get_unidad_base(self, obj):
        return UNIDAD_BASE[obj.insumo.tipo_medida]

    def get_fecha_ingreso(self, obj):
        return fecha_iso(obj.fecha_ingreso)

    def get_dias_para_vencer(self, obj):
        if obj.fecha_vencimiento is None:
            return None
        return (obj.fecha_vencimiento - timezone.localdate()).days

    def get_costo_total(self, obj):
        return str(costo_total_lote(obj.cantidad_inicial, obj.costo_unitario))


class CompraSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    fecha_hora = serializers.SerializerMethodField()
    registrada_por = serializers.SerializerMethodField()
    lineas = LoteSerializer(source='lotes', many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Compra
        fields = [
            'id', 'proveedor', 'proveedor_nombre', 'fecha_hora', 'registrada_por', 'jornada',
            'numero_comprobante', 'nota', 'lineas', 'total',
        ]
        read_only_fields = fields

    def get_fecha_hora(self, obj):
        return fecha_iso(obj.fecha_hora)

    def get_registrada_por(self, obj):
        return _nombre_empleado(obj.empleado)

    def get_total(self, obj):
        return str(sum((costo_total_lote(l.cantidad_inicial, l.costo_unitario) for l in obj.lotes.all()), Decimal('0.00')))


class LineaCompraSerializer(serializers.Serializer):
    """Una linea de compra. La cantidad se indica de UNA de estas dos formas (siempre en unidad base):
    - `cantidad` total (ej. 150000 g), o
    - `cantidad_presentaciones` x `tamano_presentacion` (ej. 10 bolsas de 15000 g)."""
    insumo = serializers.PrimaryKeyRelatedField(queryset=Insumo.objects.filter(activo=True))
    cantidad = serializers.DecimalField(required=False, **CANTIDAD)
    cantidad_presentaciones = serializers.IntegerField(required=False, min_value=1)
    tamano_presentacion = serializers.DecimalField(required=False, **CANTIDAD)
    costo_total = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True)

    def validate_fecha_vencimiento(self, value):
        if value is not None and value < timezone.localdate():
            raise serializers.ValidationError('El lote ya esta vencido: la fecha de vencimiento no puede ser pasada.')
        return value

    def validate(self, data):
        directa = 'cantidad' in data
        por_presentacion = 'cantidad_presentaciones' in data or 'tamano_presentacion' in data
        if directa == por_presentacion:
            raise serializers.ValidationError(
                'Indicar la cantidad de UNA forma: `cantidad`, o `cantidad_presentaciones` junto con `tamano_presentacion`.'
            )
        if por_presentacion:
            if 'cantidad_presentaciones' not in data or 'tamano_presentacion' not in data:
                raise serializers.ValidationError(
                    'Hacen falta `cantidad_presentaciones` y `tamano_presentacion` juntas.'
                )
            data['cantidad'] = cuantizar_cantidad(data['tamano_presentacion'] * data['cantidad_presentaciones'])
        else:
            data['cantidad'] = cuantizar_cantidad(data['cantidad'])
        if data['cantidad'] > Decimal('999999999.999'):
            raise serializers.ValidationError('La cantidad es demasiado grande.')
        if data['insumo'].tipo_medida == 'Unidad' and not es_entera(data['cantidad']):
            raise serializers.ValidationError(
                {'cantidad': f"{data['insumo'].nombre} se mide en unidades: la cantidad tiene que ser un numero entero."}
            )
        return data


class CompraCrearSerializer(serializers.Serializer):
    proveedor = serializers.PrimaryKeyRelatedField(queryset=Proveedor.objects.filter(activo=True))
    numero_comprobante = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    nota = serializers.CharField(max_length=300, required=False, allow_null=True, allow_blank=True)
    lineas = LineaCompraSerializer(many=True, allow_empty=False, max_length=100)

    def validate(self, data):
        return _limpiar_textos(data, ('numero_comprobante', 'nota'))


class MovimientoSerializer(serializers.ModelSerializer):
    insumo = serializers.IntegerField(source='lote.insumo_id', read_only=True)
    insumo_nombre = serializers.CharField(source='lote.insumo.nombre', read_only=True)
    unidad_base = serializers.SerializerMethodField()
    fecha_hora = serializers.SerializerMethodField()
    registrado_por = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoStock
        fields = [
            'id', 'lote', 'insumo', 'insumo_nombre', 'unidad_base', 'tipo', 'cantidad', 'fecha_hora', 'registrado_por',
            'jornada', 'comanda', 'motivo', 'nota',
        ]
        read_only_fields = fields

    def get_unidad_base(self, obj):
        return UNIDAD_BASE[obj.lote.insumo.tipo_medida]

    def get_fecha_hora(self, obj):
        return fecha_iso(obj.fecha_hora)

    def get_registrado_por(self, obj):
        return _nombre_empleado(obj.empleado) or 'Sistema'


# ==================== AJUSTES Y BAJAS ====================

class MotivoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=100)

    def validate_motivo(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El motivo no puede estar vacio.')
        return value


class AjusteStockSerializer(MotivoSerializer):
    insumo = serializers.PrimaryKeyRelatedField(queryset=Insumo.objects.filter(activo=True))
    cantidad_real = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0'))

    def validate(self, data):
        if data['insumo'].tipo_medida == 'Unidad' and not es_entera(data['cantidad_real']):
            raise serializers.ValidationError(
                {'cantidad_real': f"{data['insumo'].nombre} se mide en unidades: tiene que ser un numero entero."}
            )
        return data


def describir_cantidad(valor, tipo_medida):
    """Texto para mostrar (ej. '150 kg') junto al valor en unidad base."""
    return texto_cantidad(valor, tipo_medida)
