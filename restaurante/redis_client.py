import redis

from decouple import config

# IP numerica por defecto: en Windows 'localhost' puede sumar ~2 s al abrir cada conexion nueva.
# En Docker se define REDIS_HOST=redis (nombre del servicio).
REDIS_HOST = config('REDIS_HOST', default='127.0.0.1')
REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)


def nuevo_cliente():
    """Un cliente de Redis con su propio pool de conexiones (los flujos en tiempo real usan uno cada uno)."""
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


redis_client = nuevo_cliente()
