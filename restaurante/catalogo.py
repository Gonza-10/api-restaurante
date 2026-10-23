from .redis_client import redis_client


def invalidar_cache_catalogo():
    """Borra el catalogo cacheado en Redis. Hay que llamarla cuando cambia algo que el catalogo muestra:
    productos, especiales o la jornada abierta (los especiales vigentes dependen de ella)."""
    redis_client.delete('catalogo:productos:publico', 'catalogo:productos:admin')
