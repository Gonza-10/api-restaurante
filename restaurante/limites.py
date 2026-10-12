"""Limite de intentos fallidos (anti fuerza bruta) con contadores en Redis.
Si Redis no responde, el limite se desactiva pero la API sigue funcionando."""
from redis.exceptions import RedisError

from .redis_client import redis_client


def superado(clave, maximo):
    try:
        return int(redis_client.get(clave) or 0) >= maximo
    except RedisError:
        return False


def registrar_fallo(clave, ventana_segundos):
    try:
        if redis_client.incr(clave) == 1:
            redis_client.expire(clave, ventana_segundos)
    except RedisError:
        pass


def limpiar(clave):
    try:
        redis_client.delete(clave)
    except RedisError:
        pass
