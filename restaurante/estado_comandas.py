"""Estado de las comandas aceptadas en Redis (retenida, pendiente, proceso, listo). Una comanda entregada o cancelada ya no
tiene clave. Los cambios que dependen del estado de partida (cancelar, liberar la primera ronda, avanzar en cocina) se hacen
de forma atomica con WATCH: si la cocina la mueve justo cuando otro intenta cancelarla, solo uno de los dos gana."""
import redis

from .redis_client import redis_client


def clave_de(uuid_comanda):
    return f'comanda:estado:{uuid_comanda}'


def estado_de(uuid_comanda):
    """Estado en Redis, o None si ya fue entregada, se cancelo o nunca existio."""
    return redis_client.get(clave_de(uuid_comanda))


def transicionar(uuid_comanda, desde, nuevo, cliente=None):
    """Pasa la comanda a `nuevo` solo si su estado actual esta en `desde` (None = cualquier estado existente). `nuevo=None`
    borra la clave (entregada o cancelada). Devuelve (cambio, estado_anterior); si no existe o el estado no corresponde,
    no toca nada y cambio=False."""
    cliente = cliente or redis_client
    clave = clave_de(uuid_comanda)
    with cliente.pipeline() as pipe:
        for _ in range(5):
            try:
                pipe.watch(clave)
                actual = pipe.get(clave)
                if actual is None or (desde is not None and actual not in desde):
                    pipe.unwatch()
                    return False, actual
                pipe.multi()
                if nuevo is None:
                    pipe.delete(clave)
                else:
                    pipe.set(clave, nuevo)
                pipe.execute()
                return True, actual
            except redis.WatchError:
                continue   # alguien la cambio entre la lectura y la escritura: se vuelve a evaluar
    return False, cliente.get(clave)
