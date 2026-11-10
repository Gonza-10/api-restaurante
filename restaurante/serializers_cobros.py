"""Serializers de cobros, caja y cotizacion (solo lectura por ahora)."""
from decimal import Decimal

from rest_framework import serializers

from .models import Caja, MovimientoCaja


class CotizacionSerializer(serializers.Serializer):
    moneda = serializers.CharField()
    valor = serializers.DecimalField(max_digits=18, decimal_places=8, allow_null=True)   # ARS por 1 unidad; null si aun no hay
    fecha = serializers.DateField(allow_null=True)               # dia al que corresponde la cotizacion
    actualizada_en = serializers.DateTimeField(allow_null=True)  # cuando la guardamos
    fuente = serializers.CharField(allow_null=True)


class EstadoCotizacionesSerializer(serializers.Serializer):
    moneda_base = serializers.CharField()
    unidad = serializers.CharField()
    cotizaciones = CotizacionSerializer(many=True)
    ultima_consulta = serializers.DateTimeField(allow_null=True)   # ultima consulta exitosa al BCRA
    desactualizada = serializers.BooleanField()                    # True si hace mas de 2 horas que no se consulta con exito
    ultimo_error = serializers.CharField(required=False)  # solo para Admin y Gerente; sin allow_null: asi DRF omite la clave si no viene (con allow_null la mostraba como null)


# ==================== CAJA ====================

def en_texto(valor):
    """Los montos de dinero salen como texto ('10000.00'), igual que los DecimalField: asi un float no pierde centavos.
    Recorre diccionarios, listas y tuplas. Un monto sin decimales ('0', '1500') sale con dos ('0.00'); las cotizaciones,
    que tienen mas decimales, no se tocan."""
    if isinstance(valor, Decimal):
        if valor.as_tuple().exponent > -2:
            valor = valor.quantize(Decimal('0.01'))
        return format(valor, 'f')
    if isinstance(valor, dict):
        return {k: en_texto(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [en_texto(v) for v in valor]
    return valor


def _nombre(empleado):
    return f'{empleado.nombre} {empleado.apellido}' if empleado else None


class MovimientoCajaSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoCaja
        fields = ['id', 'tipo', 'concepto', 'medio', 'moneda', 'monto', 'cotizacion', 'monto_ars', 'descripcion',
                  'fecha_hora', 'empleado', 'empleado_nombre', 'pago']
        read_only_fields = fields

    def get_empleado_nombre(self, obj):
        return _nombre(obj.empleado)


class CajaResumenSerializer(serializers.ModelSerializer):
    """Para listados: sin arqueo ni movimientos."""
    abierta_por = serializers.SerializerMethodField()
    cerrada_por = serializers.SerializerMethodField()

    class Meta:
        model = Caja
        fields = ['id', 'estado', 'fecha_hora_apertura', 'abierta_por', 'fecha_hora_cierre', 'cerrada_por']
        read_only_fields = fields

    def get_abierta_por(self, obj):
        return _nombre(obj.empleado_apertura)

    def get_cerrada_por(self, obj):
        return _nombre(obj.empleado_cierre)


class CajaDetalleSerializer(CajaResumenSerializer):
    """Una caja con su arqueo: efectivo por moneda, Mercado Pago y el total en pesos (esperado y, si esta cerrada, informado
    y diferencia). Los montos salen como texto."""
    arqueo = serializers.SerializerMethodField()
    hay_diferencias = serializers.SerializerMethodField()

    class Meta(CajaResumenSerializer.Meta):
        fields = CajaResumenSerializer.Meta.fields + ['arqueo', 'hay_diferencias']
        read_only_fields = fields

    def _arqueo(self, obj):
        if not hasattr(obj, '_arqueo_cache'):
            from .caja import resumen_arqueo
            obj._arqueo_cache = resumen_arqueo(obj)
        return obj._arqueo_cache

    def get_arqueo(self, obj):
        return en_texto(self._arqueo(obj))

    def get_hay_diferencias(self, obj):
        from .caja_calculos import hay_diferencias_caja
        return hay_diferencias_caja(self._arqueo(obj)) if obj.estado == 'Cerrada' else None
