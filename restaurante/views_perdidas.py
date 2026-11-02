"""Vistas de las perdidas (hito 4): motivos, registro, historial y resumen."""
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, COCINA
from .models import Perdida
from .perdidas import (
    ProductoSinReceta, armar_perdida, consumos_por_perdida, registrar_perdida_insumo, registrar_perdida_plato,
    valor_de_perdida,
)
from .serializers_perdidas import PerdidaEntradaSerializer
from .stock import StockInsuficiente
from .stock_calculos import CODIGOS_MOTIVO, ETIQUETA_MOTIVO, MOTIVO_OTRO, resumen_perdidas, texto_cantidad
from .views_stock import _entero, _filtrar_fechas

TIPO_A_ALCANCE = {'insumo': 'Insumo', 'plato': 'Plato'}


def _consulta_base():
    return Perdida.objects.select_related('insumo', 'producto', 'empleado').order_by('-fecha_hora', '-id')


class MotivosPerdidaView(APIView):
    """GET /perdidas/motivos. La lista cerrada de motivos, para armar el desplegable del formulario. Cocina, Admin y Gerente."""
    roles_lectura = COCINA

    def get(self, request):
        return Response([
            {'codigo': codigo, 'etiqueta': ETIQUETA_MOTIVO[codigo], 'requiere_nota': codigo == MOTIVO_OTRO}
            for codigo in CODIGOS_MOTIVO
        ])


class PerdidaViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Perdidas con motivo. Cocina, Admin y Gerente cargan y consultan; el VALOR (y los costos) solo lo ven Admin y
    Gerente. No se editan ni se borran: un error se corrige con un ajuste de stock.
    - POST /perdidas: ver PerdidaEntradaSerializer. Descuenta del stock por FEFO, todo o nada (409 si no alcanza).
    - GET /perdidas (mas nuevas primero). Filtros: ?tipo=insumo|plato, ?motivo=codigo, ?insumo=id, ?producto=id,
      ?desde=AAAA-MM-DD, ?hasta=AAAA-MM-DD, ?limite=N (por defecto 200, maximo 1000).
    - GET /perdidas/<id>: ademas, de que insumos y lotes salio."""
    serializer_class = PerdidaEntradaSerializer
    roles_lectura = COCINA
    roles_escritura = COCINA

    def get_queryset(self):
        return _consulta_base()

    def list(self, request, *args, **kwargs):
        p = request.query_params
        consulta = self.get_queryset()
        if p.get('tipo'):
            tipo = p['tipo'].strip().lower()
            if tipo not in TIPO_A_ALCANCE:
                raise ValidationError({'tipo': "Valores validos: 'insumo' o 'plato'."})
            consulta = consulta.filter(alcance=TIPO_A_ALCANCE[tipo])
        if p.get('motivo'):
            motivo = p['motivo'].strip().lower()
            if motivo not in CODIGOS_MOTIVO:
                raise ValidationError({'motivo': f"Valores validos: {', '.join(CODIGOS_MOTIVO)}."})
            consulta = consulta.filter(motivo=motivo)
        if p.get('insumo'):
            consulta = consulta.filter(insumo_id=_entero(p['insumo'], 'insumo'))
        if p.get('producto'):
            consulta = consulta.filter(producto_id=_entero(p['producto'], 'producto'))
        consulta = _filtrar_fechas(consulta, p, 'fecha_hora')
        limite = min(_entero(p.get('limite', 200), 'limite', minimo=1), 1000)
        perdidas = list(consulta[:limite])
        ve_costos = request.user.rol in ADMIN_GERENTE
        consumos = consumos_por_perdida([x.id for x in perdidas]) if ve_costos else {}
        return Response([armar_perdida(x, consumos.get(x.id, []), ve_costos) for x in perdidas])

    def retrieve(self, request, *args, **kwargs):
        perdida = self.get_object()
        ve_costos = request.user.rol in ADMIN_GERENTE
        consumos = consumos_por_perdida([perdida.id])
        return Response(armar_perdida(perdida, consumos.get(perdida.id, []), ve_costos, detalle=True))

    def create(self, request, *args, **kwargs):
        entrada = PerdidaEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        empleado = request.user.empleado
        try:
            if datos['tipo'] == 'insumo':
                perdida = registrar_perdida_insumo(
                    datos['insumo'], datos['cantidad'], datos['motivo'], datos['nota'], empleado
                )
            else:
                perdida = registrar_perdida_plato(
                    datos['producto'], datos['cantidad'], datos['motivo'], datos['nota'], empleado
                )
        except ProductoSinReceta as error:
            raise ValidationError({'producto': str(error)})
        except StockInsuficiente as error:
            return Response({'error': (
                f'No alcanza el stock registrado de {error.insumo.nombre} (hay '
                f'{texto_cantidad(error.disponible, error.insumo.tipo_medida)} y se necesitan '
                f'{texto_cantidad(error.pedido, error.insumo.tipo_medida)}). No se registro nada. Si ya se perdio '
                f'fisicamente, avisar a un Admin o Gerente para que corrija el stock con un ajuste.'
            )}, status=status.HTTP_409_CONFLICT)
        perdida = self.get_queryset().get(pk=perdida.pk)
        ve_costos = request.user.rol in ADMIN_GERENTE
        consumos = consumos_por_perdida([perdida.id])
        return Response(
            armar_perdida(perdida, consumos.get(perdida.id, []), ve_costos, detalle=True), status=status.HTTP_201_CREATED
        )


class ResumenPerdidasView(APIView):
    """GET /perdidas/resumen. Donde y por que se pierde mas: total, reparto por motivo (con el porcentaje del valor
    perdido que explica cada uno), reparto insumo/plato y los items que mas pierden. Valorizado a costo real de los lotes.
    Admin y Gerente. Filtros: ?desde=AAAA-MM-DD, ?hasta=AAAA-MM-DD, ?limite_items=N (por defecto 10)."""
    roles_lectura = ADMIN_GERENTE

    def get(self, request):
        p = request.query_params
        consulta = _filtrar_fechas(_consulta_base(), p, 'fecha_hora')
        limite = _entero(p.get('limite_items', 10), 'limite_items', minimo=1)
        perdidas = list(consulta)
        consumos = consumos_por_perdida([x.id for x in perdidas])
        filas = []
        for x in perdidas:
            valor, completo = valor_de_perdida(consumos.get(x.id, []))
            es_insumo = x.alcance == 'Insumo'
            filas.append({
                'tipo': 'insumo' if es_insumo else 'plato',
                'id': x.insumo_id if es_insumo else x.producto_id,
                'nombre': x.insumo.nombre if es_insumo else x.producto.nombre,
                'motivo': x.motivo, 'valor': valor, 'completo': completo,
            })
        resumen = resumen_perdidas(filas, limite_items=limite)
        resumen['desde'] = p.get('desde') or None
        resumen['hasta'] = p.get('hasta') or None
        return Response(resumen)
