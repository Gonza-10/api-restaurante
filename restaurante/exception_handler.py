from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


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
        return response

    # Excepción no controlada por DRF: acá cae cualquier error
    # imprevisto (por ejemplo, un fallo de conexión con la base).
    return Response(
        {'error': 'Ocurrió un error interno del servidor.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )