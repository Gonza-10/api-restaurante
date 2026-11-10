import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def manejador_excepciones_personalizado(exc, context):
    """
    Centraliza el formato de todas las respuestas de error de la API.
    Mantiene los mensajes específicos de nuestras validaciones (400)
    tal cual los escribimos, pero estandariza los genéricos de Django
    (como el 404 que no viene traducido) y captura cualquier error
    no previsto devolviendo siempre un 500 con JSON estructurado.
    """
    response = exception_handler(exc, context)

    if response is not None:
        if response.status_code == 404:
            response.data = {'error': 'El recurso solicitado no existe.'}
        elif response.status_code == 401:
            response.data = {'error': str(response.data.get('detail', 'Autenticacion requerida. Inicie sesion.'))}
        elif response.status_code == 403:
            response.data = {'error': 'No tiene permisos para realizar esta accion.'}
        return response

    # Excepción no controlada por DRF: acá cae cualquier error
    # imprevisto (por ejemplo, un fallo de conexión con la base).
    # El detalle va a la consola del servidor (el cliente solo ve el mensaje genérico).
    logger.error('Error no controlado en %s', context.get('view').__class__.__name__, exc_info=exc)
    return Response(
        {'error': 'Ocurrió un error interno del servidor.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )