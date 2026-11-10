"""Barra y bebidas del mozo.

- Barra: el bartender ve en su tablero solo los tragos (productos con destino BARRA) y los avanza como la cocina:
  pendiente -> proceso -> listo -> entregado.
- Bebidas: las bebidas que no se preparan (destino MOZO) llegan al mozo de esa mesa en el aviso "Bebidas". El mozo solo
  confirma "Entregado" (no hay estados intermedios).
Las reglas de a que destino va cada producto estan en destinos_calculos.py.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import BARRA, SALON
from .comensales import _id_de_comanda
from .destinos_calculos import BARRA as DEST_BARRA, MOZO as DEST_MOZO
from .estado_comandas import estado_de, transicionar
from .models import ComandaRecibida
from .serializers import ComandaCocinaSerializer
from .views import ComandaEstadoUpdateView, _armar_tablero_cocina
from .views_cuenta import _es_mozo


class TableroBarraView(APIView):
    """GET /barra/tablero. Bartender, Admin y Gerente. Mismo formato que el tablero de cocina, pero solo con los tragos."""
    roles_lectura = BARRA

    def get(self, request):
        return Response(ComandaCocinaSerializer(_armar_tablero_cocina(DEST_BARRA), many=True).data)


class ComandaEstadoBarraView(ComandaEstadoUpdateView):
    """PATCH /barra/pedidos/{uuid}/estado. Igual que el de cocina, pero sobre los tragos de la comanda."""
    roles_escritura = BARRA
    destino = DEST_BARRA


class BebidasMozoView(APIView):
    """GET /mozo/bebidas. El aviso "Bebidas" del mozo: las bebidas listas para llevar a SUS mesas (un Admin o Gerente ve las de
    todas). Cada una trae la mesa, los items y la hora del pedido; el mozo la confirma con POST /pedidos/{uuid}/bebidas/entregar.
    Se consulta cada pocos segundos: lo ya entregado desaparece solo."""
    roles_lectura = SALON

    def get(self, request):
        comandas = ComandaRecibida.objects.filter(estado='Aceptada', pedido_cabecera__estado='Abierto')
        if _es_mozo(request):
            comandas = comandas.filter(pedido_cabecera__empleado_id=request.user.id)
        comandas = comandas.select_related('pedido_cabecera__mesa', 'comensal').prefetch_related('detalles__producto').order_by(
            'fecha_hora_recepcion')
        resultado = []
        for comanda in comandas:
            if estado_de(comanda.id_comanda_uuid, DEST_MOZO) != 'listo':   # retenida (espera el OK de la mesa) todavia no se avisa
                continue
            items = [{'nombre': d.producto.nombre, 'cantidad': d.cantidad} for d in comanda.detalles.all() if d.destino == DEST_MOZO]
            if not items:
                continue
            resultado.append({
                'id_comanda_uuid': str(comanda.id_comanda_uuid),
                'mesa_id': str(comanda.pedido_cabecera.mesa.numero).zfill(2),
                'numero_mesa': comanda.pedido_cabecera.mesa.numero,
                'id_sesion': comanda.pedido_cabecera_id,
                'comensal': comanda.comensal.nombre if comanda.comensal_id else None,
                'items': items,
                'timestamp': comanda.fecha_hora_recepcion,
            })
        return Response(resultado)


class BebidasEntregarView(APIView):
    """POST /pedidos/{uuid}/bebidas/entregar. El mozo confirma que llevo las bebidas a la mesa (es la unica accion que tiene).
    Un mozo solo confirma las de sus mesas. 404 si no hay bebidas por entregar, 409 si todavia esperan el OK de la mesa."""
    roles_escritura = SALON

    def post(self, request, uuid_comanda):
        id_comanda = _id_de_comanda(uuid_comanda)
        comanda = ComandaRecibida.objects.select_related('pedido_cabecera').filter(pk=id_comanda).first() if id_comanda else None
        if comanda is None or (_es_mozo(request) and comanda.pedido_cabecera.empleado_id != request.user.id):
            return Response({'error': 'No hay bebidas por entregar en esa comanda.'}, status=status.HTTP_404_NOT_FOUND)
        cambio, anterior = transicionar(uuid_comanda, ('listo',), None, destino=DEST_MOZO)
        if not cambio:
            if anterior == 'retenida':
                return Response({'error': 'Las bebidas esperan el OK de todos los comensales de la mesa.', 'codigo': 'comanda_retenida'},
                                status=status.HTTP_409_CONFLICT)
            return Response({'error': 'No hay bebidas por entregar en esa comanda.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'mensaje': 'Bebidas entregadas.', 'id_comanda_uuid': str(uuid_comanda), 'estado': 'entregado'})
