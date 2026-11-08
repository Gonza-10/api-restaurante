"""Ticket PDF de cada comanda (publico, por UUID). Reemplaza a `views.TicketPDFView`, que solo buscaba `<uuid>.pdf`: ahora los
tickets se guardan como 'MESA 2 - Pedido 1 (<uuid>).pdf' (ver `ticket_calculos.py`) y esta vista los encuentra por el UUID, y
tambien a los viejos. Las rutas siguen siendo las mismas (`/pedidos/<uuid>/ticket` y `/tickets/<uuid>.pdf`)."""
import os

from django.http import FileResponse, Http404
from rest_framework.views import APIView

from .ticket_calculos import buscar_ticket, nombre_descarga

CARPETA_TICKETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tickets')


class TicketPDFView(APIView):
    roles_lectura = None  # el cliente descarga su comprobante; sin el UUID de la comanda no se puede pedir

    def get(self, request, uuid_comanda):
        nombres = os.listdir(CARPETA_TICKETS) if os.path.isdir(CARPETA_TICKETS) else []
        nombre = buscar_ticket(nombres, uuid_comanda)
        if nombre is None:
            raise Http404('El ticket todavia no fue generado o la comanda no existe.')
        return FileResponse(open(os.path.join(CARPETA_TICKETS, nombre), 'rb'), content_type='application/pdf', filename=nombre_descarga(nombre))
