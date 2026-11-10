"""Estado de las comandas aceptadas en Redis (retenida, pendiente, proceso, listo). Una comanda entregada o cancelada ya no
tiene clave. Los cambios que dependen del estado de partida (cancelar, liberar la primera ronda, avanzar en cocina) se hacen
de forma atomica con WATCH: si la cocina la mueve justo cuando otro intenta cancelarla, solo uno de los dos gana.

Una comanda con items de varios destinos (cocina, barra, mozo) tiene una clave por destino:
- COCINA:  comanda:estado:<uuid>          (la clave de siempre)
- BARRA:   comanda:estado:<uuid>:barra
- MOZO:    comanda:estado:<uuid>:mozo     (las bebidas que lleva el mozo: nacen `listo` y se borran al confirmar la entrega)
Cada destino avanza por su cuenta; la comanda esta entregada cuando ya no queda ninguna clave."""
import redis

from .destinos_calculos import (
    BARRA, COCINA, DESTINOS, MOZO, RETENIDA, estado_al_liberar, estado_para_cancelar, estado_resumen, puede_cancelarse,
)
from .redis_client import redis_client

_SUFIJO = {COCINA: '', BARRA: ':barra', MOZO: ':mozo'}


def clave_de(uuid_comanda, destino=COCINA):
    return f'comanda:estado:{uuid_comanda}{_SUFIJO[destino]}'


def estado_de(uuid_comanda, destino=COCINA):
    """Estado en Redis de un destino de la comanda, o None si ya fue entregada, se cancelo o nunca existio."""
    return redis_client.get(clave_de(uuid_comanda, destino))


def estados_de(uuid_comanda, cliente=None):
    """{destino: estado} de lo que todavia no se entrego de la comanda (vacio si ya no queda nada)."""
    cliente = cliente or redis_client
    estados = {}
    for destino in DESTINOS:
        estado = cliente.get(clave_de(uuid_comanda, destino))
        if estado is not None:
            estados[destino] = estado
    return estados


TTL_DESPACHO_SEGUNDOS = 24 * 3600


def _clave_despacho(uuid_comanda, destino):
    return f'mozo:despachado:{uuid_comanda}:{destino}'


def marcar_despachado(uuid_comanda, destino, cliente=None):
    """Recuerda que cocina o la barra despacho (marco `entregado`) lo de ese destino: la clave de estado se borra, pero el mozo
    tiene que seguir viendo el aviso hasta confirmar que lo llevo a la mesa (ver ListosMozoView)."""
    cliente = cliente or redis_client
    cliente.set(_clave_despacho(uuid_comanda, destino), '1', ex=TTL_DESPACHO_SEGUNDOS)


def fue_despachado(uuid_comanda, destino, cliente=None):
    cliente = cliente or redis_client
    return bool(cliente.exists(_clave_despacho(uuid_comanda, destino)))


def estado_global(uuid_comanda):
    """Un solo estado para toda la comanda (el del destino mas atrasado), o None si ya se entrego todo."""
    return estado_resumen(estados_de(uuid_comanda))


def estado_cancelable(uuid_comanda):
    """Lo que ve la regla de cancelacion: retenida, pendiente (todavia se puede cancelar), proceso/listo o None."""
    return estado_para_cancelar(estados_de(uuid_comanda))


def crear(uuid_comanda, estados, cliente=None):
    """Crea las claves de una comanda recien aceptada. `estados`: {destino: estado inicial}."""
    cliente = cliente or redis_client
    for destino, estado in estados.items():
        cliente.set(clave_de(uuid_comanda, destino), estado)


def transicionar(uuid_comanda, desde, nuevo, cliente=None, destino=COCINA):
    """Pasa el destino de la comanda a `nuevo` solo si su estado actual esta en `desde` (None = cualquier estado existente).
    `nuevo=None` borra la clave (entregada o cancelada). Devuelve (cambio, estado_anterior); si no existe o el estado no
    corresponde, no toca nada y cambio=False."""
    cliente = cliente or redis_client
    clave = clave_de(uuid_comanda, destino)
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


def _sobre_todas_las_claves(uuid_comanda, aplicar, cliente=None):
    """Mira todas las claves de la comanda a la vez (WATCH) y, si `aplicar(estados)` devuelve las operaciones
    [(destino, nuevo_estado_o_None)], las ejecuta juntas. Devuelve (cambio, estados_vistos)."""
    cliente = cliente or redis_client
    claves = {destino: clave_de(uuid_comanda, destino) for destino in DESTINOS}
    with cliente.pipeline() as pipe:
        for _ in range(5):
            try:
                pipe.watch(*claves.values())
                estados = {d: pipe.get(c) for d, c in claves.items()}
                estados = {d: e for d, e in estados.items() if e is not None}
                operaciones = aplicar(estados)
                if not operaciones:
                    pipe.unwatch()
                    return False, estados
                pipe.multi()
                for destino, nuevo in operaciones:
                    if nuevo is None:
                        pipe.delete(claves[destino])
                    else:
                        pipe.set(claves[destino], nuevo)
                pipe.execute()
                return True, estados
            except redis.WatchError:
                continue
    return False, estados_de(uuid_comanda, cliente)


def liberar(uuid_comanda, cliente=None):
    """Sale la primera ronda de una mesa grupal: cada destino retenido pasa a su estado de salida (cocina y barra `pendiente`,
    bebidas del mozo `listo`). Devuelve True si algo cambio."""
    def aplicar(estados):
        return [(d, estado_al_liberar(d)) for d, e in estados.items() if e == RETENIDA]
    return _sobre_todas_las_claves(uuid_comanda, aplicar, cliente)[0]


def cancelar_todo(uuid_comanda, cliente=None):
    """Borra todas las claves de la comanda si todavia se puede cancelar (ni cocina ni barra empezaron, las bebidas no se
    llevaron). Devuelve True si se cancelo; si algun destino ya avanzo no toca nada."""
    def aplicar(estados):
        if not puede_cancelarse(estados):
            return []
        return [(d, None) for d in estados]
    return _sobre_todas_las_claves(uuid_comanda, aplicar, cliente)[0]


def entregar_todo(uuid_comanda, cliente=None):
    """Cierre forzado de la mesa: da por entregado todo lo que quede de la comanda. Devuelve True si habia algo."""
    def aplicar(estados):
        return [(d, None) for d in estados]
    return _sobre_todas_las_claves(uuid_comanda, aplicar, cliente)[0]
