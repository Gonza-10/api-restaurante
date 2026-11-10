"""Barra y bebidas del mozo.

- Barra: el bartender ve en su tablero solo los tragos (productos con destino BARRA) y los avanza como la cocina:
  pendiente -> proceso -> listo -> entregado.
- Bebidas: las bebidas que no se preparan (destino MOZO) llegan al mozo de esa mesa en el aviso "Bebidas". El mozo solo
  confirma "Entregado" (no hay estados intermedios).
- Para retirar: los platos de cocina y los tragos de la barra que ya estan listos se le avisan al mozo de esa mesa. El aviso NO
  desaparece cuando la cocina o la barra lo despachan: sigue hasta que el mozo toca "Entregado" (asi no se le pierde a quien se lo
  tiene que llevar). Eso no cambia ningun estado de la comanda: solo se recuerda en Redis que el mozo ya lo llevo.
Las reglas de a que destino va cada producto estan en destinos_calculos.py.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import BARRA, SALON
from .comensales import _id_de_comanda
from .destinos_calculos import BARRA as DEST_BARRA, COCINA as DEST_COCINA, MOZO as DEST_MOZO
from .estado_comandas import estado_de, estados_de, fue_despachado, transicionar
from .models import ComandaRecibida
from .redis_client import redis_client
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


TTL_RETIRO_SEGUNDOS = 24 * 3600


def _clave_retiro(uuid_comanda, destino):
    return f'mozo:retirado:{uuid_comanda}:{str(destino).upper()}'


class ListosMozoView(APIView):
    """GET /mozo/listos. Aviso "Para retirar" del mozo: los platos de cocina y los tragos de la barra que ya estan listos en SUS mesas
    (un Admin o Gerente ve los de todas). Es solo informativo: el mozo no cambia ningun estado, lo marca como entregado la cocina o la
    barra cuando el mozo lo retira. `destino` es 'cocina' o 'barra'. Una comanda con platos y tragos listos aparece una vez por destino.
    Cada aviso trae `despachado`: `false` mientras esta listo para retirar y `true` si la cocina o la barra ya lo marcaron entregado.
    Sigue apareciendo hasta que el mozo lo confirma con `POST /mozo/listos/{uuid}/entregado` o se cierra la mesa."""
    roles_lectura = SALON

    def get(self, request):
        comandas = ComandaRecibida.objects.filter(estado='Aceptada', pedido_cabecera__estado='Abierto')
        if _es_mozo(request):
            comandas = comandas.filter(pedido_cabecera__empleado_id=request.user.id)
        comandas = comandas.select_related('pedido_cabecera__mesa', 'comensal').prefetch_related('detalles__producto').order_by(
            'fecha_hora_recepcion')
        resultado = []
        for comanda in comandas:
            estados = estados_de(comanda.id_comanda_uuid)
            for destino in (DEST_COCINA, DEST_BARRA):
                estado_destino = estados.get(destino)
                # `listo`: esperando que el mozo lo retire. Sin clave pero despachado: cocina/barra ya lo marcó entregado y el
                # mozo todavía no confirmó que lo llevó a la mesa.
                despachado = estado_destino is None and fue_despachado(comanda.id_comanda_uuid, destino)
                if estado_destino != 'listo' and not despachado:
                    continue
                if redis_client.exists(_clave_retiro(comanda.id_comanda_uuid, destino)):
                    continue   # el mozo ya lo llevo a la mesa
                items = [{'nombre': d.producto.nombre, 'cantidad': d.cantidad} for d in comanda.detalles.all() if d.destino == destino]
                if not items:
                    continue
                resultado.append({
                    'id_comanda_uuid': str(comanda.id_comanda_uuid),
                    'destino': destino.lower(),
                    'despachado': despachado,
                    'mesa_id': str(comanda.pedido_cabecera.mesa.numero).zfill(2),
                    'numero_mesa': comanda.pedido_cabecera.mesa.numero,
                    'id_sesion': comanda.pedido_cabecera_id,
                    'comensal': comanda.comensal.nombre if comanda.comensal_id else None,
                    'items': items,
                    'timestamp': comanda.fecha_hora_recepcion,
                })
        return Response(resultado)


class ListoEntregadoMozoView(APIView):
    """POST /mozo/listos/{uuid}/entregado. El mozo confirma que llevo a la mesa los platos o tragos de ese aviso: `{"destino": "cocina"}`
    o `{"destino": "barra"}`. Solo borra el aviso del mozo (no toca el estado de la comanda). Un mozo solo confirma los de sus mesas."""
    roles_escritura = SALON

    def post(self, request, uuid_comanda):
        destino = str((request.data.get('destino') if hasattr(request.data, 'get') else '') or '').strip().upper()
        if destino not in (DEST_COCINA, DEST_BARRA):
            return Response({'error': 'El destino debe ser cocina o barra.'}, status=status.HTTP_400_BAD_REQUEST)
        id_comanda = _id_de_comanda(uuid_comanda)
        comanda = ComandaRecibida.objects.select_related('pedido_cabecera').filter(pk=id_comanda).first() if id_comanda else None
        if comanda is None or (_es_mozo(request) and comanda.pedido_cabecera.empleado_id != request.user.id):
            return Response({'error': 'No hay nada para entregar en esa comanda.'}, status=status.HTTP_404_NOT_FOUND)
        redis_client.set(_clave_retiro(uuid_comanda, destino), '1', ex=TTL_RETIRO_SEGUNDOS)
        return Response({'mensaje': 'Entregado.', 'id_comanda_uuid': str(uuid_comanda), 'destino': destino.lower()})


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
