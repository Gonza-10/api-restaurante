import redis

REDIS_HOST = '127.0.0.1'  # IP numerica: en Windows 'localhost' puede sumar ~2 s al abrir cada conexion nueva
REDIS_PORT = 6379


def nuevo_cliente():
    """Un cliente de Redis con su propio pool de conexiones (los flujos en tiempo real usan uno cada uno)."""
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


redis_client = nuevo_cliente()
