"""Vistas del hito 6: elaboraciones, producciones, vencimientos, configuracion del stock y lista de reposicion."""
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, COCINA
from .elaboraciones import (
    InsumoProducidoInactivo, ProduccionInvalida, armar_elaboracion, armar_producciones, registrar_produccion,
)
from .models import Produccion, Receta, RecetaIngrediente
from .recetas import contexto_lectura
from .reposicion import armar_reposicion
from .serializers_elaboraciones import (
    ConfiguracionStockSerializer, ElaboracionEntradaSerializer, ProduccionEntradaSerializer,
)
from .stock import StockInsuficiente
from .stock_calculos import MAX_DIAS_AVISO, MIN_DIAS_AVISO, texto_cantidad
from .vencimientos import armar_vencimientos, dias_aviso, fijar_dias_aviso, procesar_vencidos
from .views import _es_verdadero
from .views_stock import _entero, _filtrar_fechas


def _ve_costos(request):
    return request.user.rol in ADMIN_GERENTE


# ==================== ELABORACIONES ====================

class ElaboracionViewSet(viewsets.ModelViewSet):
    """Elaboraciones: recetas que cocinan un insumo propio (salsa, masa, caldo) a partir de otros insumos. Un
    ingrediente puede ser, a su vez, otra elaboracion (no se permiten ciclos). Cantidades en unidad base (g, ml o u).
    Lectura: Cocina, Admin y Gerente (Cocina ve cantidades y cuantas tandas puede hacer, sin costos).
    Escritura: Admin y Gerente. En el PUT, `ingredientes` reemplaza la lista completa.
    DELETE solo si nunca se produjo (409 si tiene producciones registradas). Filtro: ?buscar=texto.
    No se mezclan con /recetas: esas son las de los platos del menu."""
    roles_lectura = COCINA
    roles_escritura = ADMIN_GERENTE

    def get_queryset(self):
        consulta = (
            Receta.objects.filter(insumo_producido__isnull=False)
            .select_related('insumo_producido').prefetch_related('ingredientes__insumo').order_by('nombre')
        )
        if self.action == 'list':
            texto = (self.request.query_params.get('buscar') or '').strip()
            if texto:
                consulta = consulta.filter(nombre__icontains=texto)
        return consulta

    def _salida(self, recetas, ve_costos):
        recetas = list(recetas)
        disponible, costos = contexto_lectura(recetas, ve_costos)
        return [armar_elaboracion(r, ve_costos, disponible, costos) for r in recetas]

    @staticmethod
    def _guardar(receta, datos):
        receta.ingredientes.all().delete()
        RecetaIngrediente.objects.bulk_create([
            RecetaIngrediente(receta=receta, insumo=i['insumo'], cantidad=i['cantidad'], es_quitable=False)
            for i in datos['ingredientes']
        ])

    def list(self, request, *args, **kwargs):
        return Response(self._salida(self.get_queryset(), _ve_costos(request)))

    def retrieve(self, request, *args, **kwargs):
        return Response(self._salida([self.get_object()], _ve_costos(request))[0])

    def create(self, request, *args, **kwargs):
        entrada = ElaboracionEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        with transaction.atomic():
            receta = Receta.objects.create(
                nombre=datos['nombre'], descripcion=datos.get('descripcion') or None, insumo_producido=datos['insumo'],
                rinde=datos['rinde'], dias_vencimiento=datos.get('dias_vencimiento'),
            )
            self._guardar(receta, datos)
        receta = self.get_queryset().get(pk=receta.pk)
        return Response(self._salida([receta], True)[0], status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        receta = self.get_object()
        entrada = ElaboracionEntradaSerializer(receta, data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        with transaction.atomic():
            receta.nombre = datos['nombre']
            receta.descripcion = datos.get('descripcion') or None
            receta.rinde = datos['rinde']
            receta.dias_vencimiento = datos.get('dias_vencimiento')
            receta.save(update_fields=['nombre', 'descripcion', 'rinde', 'dias_vencimiento'])
            self._guardar(receta, datos)
        receta = self.get_queryset().get(pk=receta.pk)
        return Response(self._salida([receta], True)[0])

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {'error': 'Use PUT con la elaboracion completa (insumo, rinde e ingredientes).'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        receta = self.get_object()
        if receta.producciones.exists():
            return Response(
                {'error': 'Esta elaboracion ya tiene producciones registradas y no se puede borrar: el historial se conserva.'},
                status=status.HTTP_409_CONFLICT,
            )
        receta.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== PRODUCCIONES ====================

def _consulta_producciones():
    return Produccion.objects.select_related('insumo', 'empleado', 'receta').order_by('-fecha_hora', '-id')


class ProduccionViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Producciones: Cocina registra que elaboro. Cocina, Admin y Gerente cargan y consultan; el COSTO solo lo ven Admin y
    Gerente. No se editan ni se borran: un error se corrige con un ajuste de stock.
    - POST /producciones: {"elaboracion": id, "tandas": 2, "nota": "...", "fecha_vencimiento": "AAAA-MM-DD"}. Descuenta los
      ingredientes por FEFO y da de alta el lote producido con costo real. Todo o nada (409 si un ingrediente no alcanza).
    - GET /producciones (mas nuevas primero). Filtros: ?insumo=id, ?elaboracion=id, ?desde=, ?hasta=, ?limite=N (200 por
      defecto, maximo 1000).
    - GET /producciones/<id>: ademas, de que lotes salieron los ingredientes."""
    serializer_class = ProduccionEntradaSerializer
    roles_lectura = COCINA
    roles_escritura = COCINA

    def get_queryset(self):
        return _consulta_producciones()

    def list(self, request, *args, **kwargs):
        p = request.query_params
        consulta = self.get_queryset()
        if p.get('insumo'):
            consulta = consulta.filter(insumo_id=_entero(p['insumo'], 'insumo'))
        if p.get('elaboracion'):
            consulta = consulta.filter(receta_id=_entero(p['elaboracion'], 'elaboracion'))
        consulta = _filtrar_fechas(consulta, p, 'fecha_hora')
        limite = min(_entero(p.get('limite', 200), 'limite', minimo=1), 1000)
        return Response(armar_producciones(consulta[:limite], _ve_costos(request)))

    def retrieve(self, request, *args, **kwargs):
        return Response(armar_producciones([self.get_object()], _ve_costos(request), detalle=True)[0])

    def create(self, request, *args, **kwargs):
        entrada = ProduccionEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        try:
            produccion = registrar_produccion(
                datos['elaboracion'], datos['tandas'], request.user.empleado, nota=datos['nota'],
                fecha_vencimiento=datos.get('fecha_vencimiento'),
            )
        except ProduccionInvalida as error:
            return Response({'error': error.errores[0]['mensaje'], 'errores': error.errores}, status=status.HTTP_400_BAD_REQUEST)
        except InsumoProducidoInactivo as error:
            return Response({'error': f'{error} Reactivarlo antes de elaborar.'}, status=status.HTTP_409_CONFLICT)
        except StockInsuficiente as error:
            return Response({'error': (
                f'No alcanza el stock registrado de {error.insumo.nombre} (hay '
                f'{texto_cantidad(error.disponible, error.insumo.tipo_medida)} y se necesitan '
                f'{texto_cantidad(error.pedido, error.insumo.tipo_medida)}). No se registro nada.'
            )}, status=status.HTTP_409_CONFLICT)
        produccion = self.get_queryset().get(pk=produccion.pk)
        return Response(
            armar_producciones([produccion], _ve_costos(request), detalle=True)[0], status=status.HTTP_201_CREATED
        )


# ==================== VENCIMIENTOS Y CONFIGURACION ====================

class VencimientosView(APIView):
    """GET /vencimientos. Lotes que ya vencieron (y falta dar de baja) y lotes por vencer dentro de los dias de aviso,
    con los dias que faltan, el que vence antes primero. Cocina, Admin y Gerente; el valor solo Admin y Gerente."""
    roles_lectura = COCINA

    def get(self, request):
        return Response(armar_vencimientos(_ve_costos(request)))


class ProcesarVencimientosView(APIView):
    """POST /vencimientos/procesar. Da de baja todos los lotes ya vencidos como perdida con motivo 'vencimiento'
    (tambien se hace sola al abrir cada jornada). Cocina, Admin y Gerente; el valor solo Admin y Gerente."""
    roles_escritura = COCINA

    def post(self, request):
        resultado = procesar_vencidos(
            request.user.empleado, 'Baja manual de lotes vencidos', ve_costos=_ve_costos(request)
        )
        return Response(resultado)


class ConfiguracionStockView(APIView):
    """GET/PUT /configuracion/stock. `dias_aviso_vencimiento`: con cuantos dias de anticipacion se avisa que un lote esta
    por vencer (5 por defecto). Admin y Gerente."""
    roles_lectura = ADMIN_GERENTE
    roles_escritura = ADMIN_GERENTE

    @staticmethod
    def _salida():
        return {'dias_aviso_vencimiento': dias_aviso(), 'minimo': MIN_DIAS_AVISO, 'maximo': MAX_DIAS_AVISO}

    def get(self, request):
        return Response(self._salida())

    def put(self, request):
        entrada = ConfiguracionStockSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        fijar_dias_aviso(entrada.validated_data['dias_aviso_vencimiento'], request.user.empleado)
        return Response(self._salida())


# ==================== REPOSICION ====================

class ReposicionView(APIView):
    """GET /stock/reposicion. Que comprar (agrupado por proveedor principal, con costo estimado a la ultima compra) y que
    elaborar (con las tandas necesarias) para volver al stock objetivo. Por defecto solo los insumos que requieren
    atencion (agotados, criticos o bajos); ?todos=true incluye cualquiera por debajo de su objetivo. Admin y Gerente."""
    roles_lectura = ADMIN_GERENTE

    def get(self, request):
        return Response(armar_reposicion(todos=_es_verdadero(request.query_params.get('todos'))))
