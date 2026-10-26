"""Vistas del stock (hito 1): proveedores, insumos, compras, lotes, movimientos, estado del stock y ajustes."""
from datetime import timedelta

from django.db.models import OuterRef, Prefetch, Subquery
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, COCINA
from .models import Compra, Insumo, LoteInsumo, MovimientoStock, Proveedor, StockInsumo
from .serializers_stock import (
    AjusteStockSerializer, AsignarProveedoresSerializer, CompraCrearSerializer, CompraSerializer, InsumoSerializer,
    LoteSerializer, MotivoSerializer, MovimientoSerializer, ProveedorSerializer,
)
from .stock import (
    LoteNoActivo, ajustar_stock, dar_baja_lote, fijar_proveedores_de_insumo, inconsistencias_del_libro,
    proveedores_por_insumo, registrar_compra, stock_actual,
)
from .stock_calculos import (
    CERO, ESTADOS_STOCK, SEMAFORO, UNIDAD_BASE, clave_gravedad, redondear_dinero, resumen_estados, texto_cantidad,
)
from .views import _es_verdadero
from .views_operacion import _parsear_fecha

ESTADOS_LOTE = {'activo': 'Activo', 'agotado': 'Agotado', 'vencido': 'Vencido', 'baja': 'Baja'}
TIPOS_MOVIMIENTO = {
    t.lower(): t for t in ('Compra', 'Consumo', 'Perdida', 'Ajuste', 'Devolucion', 'Vencido', 'Elaboracion')
}


def _entero(valor, nombre, minimo=0):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ValidationError({nombre: 'Debe ser un numero entero.'})
    if numero < minimo:
        raise ValidationError({nombre: f'Debe ser {minimo} o mayor.'})
    return numero


def _filtrar_fechas(consulta, p, campo):
    """?desde=AAAA-MM-DD y ?hasta=AAAA-MM-DD (ambos inclusive) sobre un campo de fecha y hora."""
    if p.get('desde'):
        consulta = consulta.filter(**{f'{campo}__date__gte': _parsear_fecha(p['desde'], 'desde')})
    if p.get('hasta'):
        consulta = consulta.filter(**{f'{campo}__date__lte': _parsear_fecha(p['hasta'], 'hasta')})
    return consulta


# ==================== PROVEEDORES ====================

class ProveedorViewSet(viewsets.ModelViewSet):
    """Proveedores. Admin y Gerente. DELETE es baja logica (conserva el historial de compras).
    Filtros: ?incluir_inactivos=true, ?buscar=texto."""
    serializer_class = ProveedorSerializer
    roles_lectura = ADMIN_GERENTE
    roles_escritura = ADMIN_GERENTE

    def get_queryset(self):
        consulta = Proveedor.objects.order_by('nombre')
        if self.action == 'list':
            p = self.request.query_params
            if not _es_verdadero(p.get('incluir_inactivos')):
                consulta = consulta.filter(activo=True)
            if (p.get('buscar') or '').strip():
                consulta = consulta.filter(nombre__icontains=p['buscar'].strip())
        return consulta

    def destroy(self, request, *args, **kwargs):
        proveedor = self.get_object()
        if proveedor.activo:
            proveedor.activo = False
            proveedor.save(update_fields=['activo'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== INSUMOS ====================

class InsumoViewSet(viewsets.ModelViewSet):
    """Catalogo de insumos (materia prima). Admin y Gerente. Cada insumo trae su stock actual, porcentaje y semaforo.
    DELETE es baja logica y solo si no tiene stock (primero hay que ajustarlo a cero).
    Filtros: ?incluir_inactivos=true, ?buscar=texto, ?tipo_medida=Masa|Volumen|Unidad."""
    serializer_class = InsumoSerializer
    roles_lectura = ADMIN_GERENTE
    roles_escritura = ADMIN_GERENTE

    def get_queryset(self):
        consulta = Insumo.objects.order_by('nombre')
        if self.action == 'list':
            p = self.request.query_params
            if not _es_verdadero(p.get('incluir_inactivos')):
                consulta = consulta.filter(activo=True)
            if (p.get('buscar') or '').strip():
                consulta = consulta.filter(nombre__icontains=p['buscar'].strip())
            if p.get('tipo_medida'):
                consulta = consulta.filter(tipo_medida__iexact=p['tipo_medida'].strip())
        return consulta

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        contexto.update(getattr(self, '_contexto_listado', {}))
        return contexto

    def list(self, request, *args, **kwargs):
        insumos = list(self.filter_queryset(self.get_queryset()))
        ids = [i.id for i in insumos]
        self._contexto_listado = {
            'stock_por_insumo': {f.insumo_id: f for f in StockInsumo.objects.filter(insumo_id__in=ids)},
            'proveedores_por_insumo': proveedores_por_insumo(ids),
        }
        return Response(self.get_serializer(insumos, many=True).data)

    def destroy(self, request, *args, **kwargs):
        insumo = self.get_object()
        if insumo.activo:
            if stock_actual(insumo.id) > 0:
                return Response(
                    {'error': 'El insumo todavia tiene stock. Ajustarlo a cero antes de darlo de baja.'},
                    status=status.HTTP_409_CONFLICT
                )
            insumo.activo = False
            insumo.save(update_fields=['activo'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['put'], url_path='proveedores')
    def proveedores(self, request, pk=None):
        """PUT /insumos/<id>/proveedores. Reemplaza los proveedores del insumo:
        {"proveedores": [{"proveedor": 1, "es_principal": true}, {"proveedor": 2}]}. Lista vacia = sin proveedores."""
        insumo = self.get_object()
        entrada = AsignarProveedoresSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        fijar_proveedores_de_insumo(
            insumo.id, [(item['proveedor'].id, item['es_principal']) for item in entrada.validated_data['proveedores']]
        )
        return Response(self.get_serializer(insumo).data)


# ==================== COMPRAS ====================

class CompraViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Compras a proveedores (el historial de compras). Admin y Gerente. No se editan ni se borran: un error se
    corrige con un ajuste de stock. Cada linea de la compra crea un lote.
    Filtros: ?proveedor=id, ?insumo=id, ?desde=AAAA-MM-DD, ?hasta=AAAA-MM-DD."""
    roles_lectura = ADMIN_GERENTE
    roles_escritura = ADMIN_GERENTE

    def get_serializer_class(self):
        return CompraCrearSerializer if self.action == 'create' else CompraSerializer

    def get_queryset(self):
        consulta = (
            Compra.objects.select_related('proveedor', 'empleado')
            .prefetch_related(Prefetch('lotes', queryset=LoteInsumo.objects.select_related('insumo').order_by('id')))
            .order_by('-fecha_hora', '-id')
        )
        if self.action == 'list':
            p = self.request.query_params
            if p.get('proveedor'):
                consulta = consulta.filter(proveedor_id=_entero(p['proveedor'], 'proveedor'))
            if p.get('insumo'):
                consulta = consulta.filter(lotes__insumo_id=_entero(p['insumo'], 'insumo')).distinct()
            consulta = _filtrar_fechas(consulta, p, 'fecha_hora')
        return consulta

    def create(self, request, *args, **kwargs):
        entrada = CompraCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        compra = registrar_compra(
            proveedor=datos['proveedor'], empleado=request.user.empleado, lineas=datos['lineas'],
            numero_comprobante=datos.get('numero_comprobante'), nota=datos.get('nota'),
        )
        compra = self.get_queryset().get(pk=compra.pk)
        return Response(CompraSerializer(compra).data, status=status.HTTP_201_CREATED)


# ==================== LOTES ====================

class LoteViewSet(viewsets.ReadOnlyModelViewSet):
    """Lotes de insumos. Admin y Gerente.
    Filtros: ?insumo=id, ?estado=activo|agotado|vencido|baja, ?vence_en_dias=N (activos que vencen en N dias o menos)."""
    serializer_class = LoteSerializer
    roles_lectura = ADMIN_GERENTE
    roles_escritura = ADMIN_GERENTE

    def get_queryset(self):
        consulta = LoteInsumo.objects.select_related('insumo').order_by('-fecha_ingreso', '-id')
        if self.action == 'list':
            p = self.request.query_params
            if p.get('insumo'):
                consulta = consulta.filter(insumo_id=_entero(p['insumo'], 'insumo'))
            if p.get('estado'):
                estado = ESTADOS_LOTE.get(p['estado'].strip().lower())
                if estado is None:
                    raise ValidationError({'estado': "Valores validos: 'activo', 'agotado', 'vencido' o 'baja'."})
                consulta = consulta.filter(estado=estado)
            if p.get('vence_en_dias'):
                limite = timezone.localdate() + timedelta(days=_entero(p['vence_en_dias'], 'vence_en_dias'))
                consulta = consulta.filter(estado='Activo', fecha_vencimiento__isnull=False, fecha_vencimiento__lte=limite)
        return consulta

    @action(detail=True, methods=['post'], url_path='baja')
    def baja(self, request, pk=None):
        """POST /lotes/<id>/baja {"motivo": "..."}. Saca del stock lo que quedaba del lote y lo marca Baja
        (o Vencido, si ya vencio). Queda en el libro de movimientos."""
        lote = self.get_object()
        entrada = MotivoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            dar_baja_lote(lote.id, request.user.empleado, entrada.validated_data['motivo'])
        except LoteNoActivo as error:
            return Response({'error': str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(LoteSerializer(self.get_queryset().get(pk=lote.pk)).data)


# ==================== LIBRO DE MOVIMIENTOS ====================

class MovimientoStockViewSet(viewsets.ReadOnlyModelViewSet):
    """Libro de movimientos de stock (solo lectura, mas nuevos primero). Admin y Gerente.
    Filtros: ?insumo=id, ?lote=id, ?tipo=compra|consumo|perdida|ajuste|devolucion|vencido|elaboracion,
    ?desde=, ?hasta=, ?limite=N (por defecto 200, maximo 1000)."""
    serializer_class = MovimientoSerializer
    roles_lectura = ADMIN_GERENTE

    def get_queryset(self):
        return MovimientoStock.objects.select_related('lote__insumo', 'empleado').order_by('-fecha_hora', '-id')

    def list(self, request, *args, **kwargs):
        p = request.query_params
        consulta = self.get_queryset()
        if p.get('insumo'):
            consulta = consulta.filter(lote__insumo_id=_entero(p['insumo'], 'insumo'))
        if p.get('lote'):
            consulta = consulta.filter(lote_id=_entero(p['lote'], 'lote'))
        if p.get('tipo'):
            tipo = TIPOS_MOVIMIENTO.get(p['tipo'].strip().lower())
            if tipo is None:
                raise ValidationError({'tipo': f"Valores validos: {', '.join(t.lower() for t in TIPOS_MOVIMIENTO.values())}."})
            consulta = consulta.filter(tipo=tipo)
        consulta = _filtrar_fechas(consulta, p, 'fecha_hora')
        limite = min(_entero(p.get('limite', 200), 'limite', minimo=1), 1000)
        return Response(self.get_serializer(list(consulta[:limite]), many=True).data)


# ==================== ESTADO DEL STOCK ====================

class StockView(APIView):
    """GET /stock. Estado del stock insumo por insumo, con el mas grave primero (agotado, critico, bajo, ...).
    Cocina, Admin y Gerente. NO hay un porcentaje general: un promedio taparia un insumo esencial en rojo.
    - ?vista=resumida (por defecto): cada insumo con su porcentaje y semaforo.
    - ?vista=detallada: ademas cuanto hay de cada uno, el objetivo, los umbrales, lotes y proximo vencimiento.
      Admin y Gerente ven ademas costos, valor del stock y proveedor principal; Cocina no.
    Filtros: ?estado=agotado,critico,bajo,sinobjetivo,ok (varios, separados por coma) y ?buscar=texto.
    `resumen` cuenta los insumos por estado sobre todos los que coinciden con ?buscar (no cambia con ?estado)."""
    roles_lectura = COCINA

    def get(self, request):
        p = request.query_params
        vista = (p.get('vista') or 'resumida').strip().lower()
        if vista not in ('resumida', 'detallada'):
            raise ValidationError({'vista': "Valores validos: 'resumida' o 'detallada'."})
        ve_costos = request.user.rol in ADMIN_GERENTE

        filtro_estados = None
        if (p.get('estado') or '').strip():
            por_minuscula = {e.lower(): e for e in ESTADOS_STOCK}
            pedidos = [x.strip().lower() for x in p['estado'].split(',') if x.strip()]
            desconocidos = [x for x in pedidos if x not in por_minuscula]
            if desconocidos:
                raise ValidationError({'estado': f"Valores validos: {', '.join(e.lower() for e in ESTADOS_STOCK)}."})
            filtro_estados = {por_minuscula[x] for x in pedidos}

        filas = StockInsumo.objects.filter(activo=True)
        if (p.get('buscar') or '').strip():
            filas = filas.filter(nombre__icontains=p['buscar'].strip())
        filas = list(filas)
        resumen = resumen_estados([f.estado for f in filas])
        if filtro_estados is not None:
            filas = [f for f in filas if f.estado in filtro_estados]
        filas.sort(key=lambda f: clave_gravedad(f.estado, f.porcentaje, f.nombre))

        extra = self._detalle([f.insumo_id for f in filas], ve_costos) if vista == 'detallada' else {}
        insumos = []
        for f in filas:
            item = {
                'id': f.insumo_id,
                'nombre': f.nombre,
                'porcentaje': float(f.porcentaje) if f.porcentaje is not None else None,
                'estado': f.estado,
                'semaforo': SEMAFORO[f.estado],
            }
            if vista == 'detallada':
                item.update({
                    'tipo_medida': f.tipo_medida,
                    'unidad_base': UNIDAD_BASE[f.tipo_medida],
                    'stock_actual': str(f.stock_actual),
                    'stock_actual_texto': texto_cantidad(f.stock_actual, f.tipo_medida),
                    'stock_objetivo': str(f.stock_objetivo),
                    'stock_objetivo_texto': texto_cantidad(f.stock_objetivo, f.tipo_medida),
                    'umbral_bajo_pct': f.umbral_bajo_pct,
                    'umbral_critico_pct': f.umbral_critico_pct,
                })
                item.update(extra[f.insumo_id])
            insumos.append(item)
        return Response({'vista': vista, 'resumen': resumen, 'insumos': insumos})

    def _detalle(self, ids, ve_costos):
        """Datos de la vista detallada: lotes, proximo vencimiento y, solo para Admin y Gerente, costos y proveedor."""
        hoy = timezone.localdate()
        datos = {
            i: {'lotes_activos': 0, 'proximo_vencimiento': None, 'dias_para_vencer': None}
            for i in ids
        }
        valores = {i: CERO for i in ids}
        lotes = LoteInsumo.objects.filter(insumo_id__in=ids, estado='Activo', cantidad_actual__gt=0).values(
            'insumo_id', 'cantidad_actual', 'costo_unitario', 'fecha_vencimiento'
        )
        for lote in lotes:
            d = datos[lote['insumo_id']]
            d['lotes_activos'] += 1
            valores[lote['insumo_id']] += lote['cantidad_actual'] * lote['costo_unitario']
            vence = lote['fecha_vencimiento']
            if vence is not None and (d['proximo_vencimiento'] is None or vence < d['proximo_vencimiento']):
                d['proximo_vencimiento'] = vence
        for d in datos.values():
            if d['proximo_vencimiento'] is not None:
                d['dias_para_vencer'] = (d['proximo_vencimiento'] - hoy).days
                d['proximo_vencimiento'] = d['proximo_vencimiento'].isoformat()

        if ve_costos and ids:
            costos = dict(
                Insumo.objects.filter(id__in=ids).annotate(
                    ultimo=Subquery(
                        LoteInsumo.objects.filter(insumo=OuterRef('pk'), origen='Compra')
                        .order_by('-fecha_ingreso', '-id').values('costo_unitario')[:1]
                    )
                ).values_list('id', 'ultimo')
            )
            proveedores = proveedores_por_insumo(ids)
            for i in ids:
                datos[i]['costo_reposicion'] = str(costos[i]) if costos.get(i) is not None else None
                datos[i]['valor_stock'] = str(redondear_dinero(valores[i]))
                principal = next((p for p in proveedores.get(i, []) if p['es_principal']), None)
                datos[i]['proveedor_principal'] = (
                    {'id': principal['id'], 'nombre': principal['nombre']} if principal else None
                )
        return datos


class AjusteStockView(APIView):
    """POST /stock/ajustes {"insumo": id, "cantidad_real": N, "motivo": "..."}. Ajuste por inventario: deja el stock
    del insumo en la cantidad que se conto (en unidad base). Si hay menos, descuenta por FEFO; si hay mas, crea un lote
    de origen 'Ajuste' con el costo del ultimo lote comprado. Admin y Gerente."""
    roles_lectura = ADMIN_GERENTE
    roles_escritura = ADMIN_GERENTE

    def post(self, request):
        entrada = AjusteStockSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        insumo = entrada.validated_data['insumo']
        anterior, diferencia, movimientos = ajustar_stock(
            insumo, entrada.validated_data['cantidad_real'], request.user.empleado, entrada.validated_data['motivo']
        )
        ids = [m.id for m in movimientos]
        guardados = MovimientoStock.objects.select_related('lote__insumo', 'empleado').filter(id__in=ids).order_by('id')
        return Response({
            'insumo': insumo.id,
            'nombre': insumo.nombre,
            'unidad_base': UNIDAD_BASE[insumo.tipo_medida],
            'stock_anterior': str(anterior),
            'stock_nuevo': str(entrada.validated_data['cantidad_real']),
            'diferencia': str(diferencia),
            'movimientos': MovimientoSerializer(guardados, many=True).data,
        })


class VerificacionLibroView(APIView):
    """GET /stock/verificacion. Comprueba la regla del libro: la suma de los movimientos de cada lote tiene que ser
    igual a su cantidad actual. Admin y Gerente."""
    roles_lectura = ADMIN_GERENTE

    def get(self, request):
        malos = inconsistencias_del_libro()
        return Response({'consistente': not malos, 'lotes_inconsistentes': malos})
