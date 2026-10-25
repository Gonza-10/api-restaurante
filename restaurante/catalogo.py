"""Cache y version del menu.

Cada cambio que el cliente ve en el menu (productos, categorias, especiales, jornada, disponibilidad) llama a
invalidar_cache_catalogo(): sube un contador de VERSION y avisa por Redis (pub/sub).

La version es la fuente de verdad:
- el cache del listado guarda cada copia bajo una clave que incluye la version (clave_cache_catalogo), asi una
  copia vieja nunca puede quedar sirviendose despues de un cambio, ni siquiera si una consulta que empezo antes
  del cambio termina de guardarse despues (guardaria en la clave de la version anterior, que ya nadie lee);
- el flujo SSE (/catalogo/eventos) y /catalogo/version la leen, asi un aviso perdido nunca deja a un cliente
  con el menu viejo.
"""
import logging
from decimal import Decimal, InvalidOperation

from .redis_client import redis_client

CLAVE_VERSION = 'catalogo:version'
CANAL_CAMBIOS = 'catalogo:cambios'

PRECIOS_TTL_SEG = 24 * 3600      # cuanto se recuerdan los precios de la version vigente del menu
PRECIOS_GRACIA_SEG = 2 * 3600    # cuanto se siguen respetando despues de que el menu cambia (carritos armados)

logger = logging.getLogger(__name__)


def version_catalogo():
    """Version actual del menu (0 si nunca cambio desde que arranco Redis)."""
    return int(redis_client.get(CLAVE_VERSION) or 0)


def clave_cache_catalogo(vista, version):
    """Clave del cache del listado para una version del menu. vista: 'publico' o 'admin'."""
    return f'catalogo:productos:{vista}:v{version}'


def invalidar_cache_catalogo():
    """Marca el menu como cambiado: sube la version (con eso el cache anterior deja de usarse; vence solo por su
    TTL) y avisa a los clientes conectados. Hay que llamarla DESPUES de guardar el cambio en la base.
    Si Redis falla no se tumba la operacion que ya se guardo: se registra el error."""
    try:
        version = redis_client.incr(CLAVE_VERSION)
        # los clientes que armaron su pedido con la version anterior tienen un plazo para confirmarlo a esos precios
        redis_client.expire(_clave_precios(version - 1), PRECIOS_GRACIA_SEG)
        redis_client.publish(CANAL_CAMBIOS, str(version))
    except Exception:
        logger.exception('No se pudo avisar el cambio del catalogo')


def _clave_precios(version):
    return f'catalogo:precios:v{version}'


def guardar_precios_vistos(version, precios):
    """Recuerda que precio mostraba el menu en una version: {id_producto: 'NN.NN'} (el especial si lo habia).
    Permite cobrar el precio que el cliente vio aunque cambie mientras arma el pedido. Nunca rompe el listado."""
    if not precios:
        return
    try:
        clave = _clave_precios(version)
        redis_client.hset(clave, mapping={str(id_producto): str(precio) for id_producto, precio in precios.items()})
        if redis_client.ttl(clave) < 0:  # sin vencimiento: se lo ponemos (no se alarga el de versiones ya vencidas)
            redis_client.expire(clave, PRECIOS_TTL_SEG)
    except Exception:
        logger.exception('No se pudieron guardar los precios vistos')


def precios_vistos(version):
    """Precios que mostraba el menu en esa version: {id_producto: Decimal}. Vacio si la version es desconocida o ya
    vencio su plazo (entonces se cobra el precio vigente). El cliente solo informa la version, nunca un precio."""
    try:
        crudos = redis_client.hgetall(_clave_precios(version))
    except Exception:
        logger.exception('No se pudieron leer los precios vistos')
        return {}
    resultado = {}
    for id_producto, precio in crudos.items():
        try:
            resultado[int(id_producto)] = Decimal(precio)
        except (ValueError, InvalidOperation):
            continue
    return resultado
