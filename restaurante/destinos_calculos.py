"""Reglas puras de los destinos de un pedido (sin Django ni Redis, para poder probarlas solas).

Cada producto se prepara o se entrega en un destino:
- COCINA: lo ve el tablero de cocina (la regla por defecto: entradas, principales, postres...).
- BARRA: lo prepara el bartender y lo ve el tablero de la barra (los tragos).
- MOZO: no se prepara, solo se lleva a la mesa; el mozo de esa mesa recibe el aviso "Bebidas" y confirma la entrega (las bebidas).

El destino sale de la categoria del producto (Tragos -> BARRA, Bebidas -> MOZO, el resto -> COCINA) salvo que el producto tenga
uno propio cargado, que gana. Una comanda con items de varios destinos se divide: cada destino tiene su propio estado.
"""
import unicodedata

COCINA = 'COCINA'
BARRA = 'BARRA'
MOZO = 'MOZO'
DESTINOS = (COCINA, BARRA, MOZO)

RETENIDA = 'retenida'
PENDIENTE = 'pendiente'
PROCESO = 'proceso'
LISTO = 'listo'
ENTREGADO = 'entregado'

# orden en que avanza un pedido; la comanda se muestra con el estado del destino mas atrasado
ORDEN_ESTADOS = (RETENIDA, PENDIENTE, PROCESO, LISTO)

_TRAGOS = ('trago', 'coctel', 'cocktail', 'tragos')
_BEBIDAS = ('bebida', 'gaseosa', 'cerveza', 'vino', 'agua', 'jugo')


def _sin_acentos(texto):
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in descompuesto if not unicodedata.combining(c)).strip().casefold()


def destino_valido(texto):
    """'COCINA', 'BARRA' o 'MOZO' (sin importar mayusculas ni espacios), o None si no es un destino."""
    limpio = (texto or '').strip().upper()
    return limpio if limpio in DESTINOS else None


def destino_por_categoria(nombre_categoria):
    """Destino que le corresponde a una categoria por su nombre: tragos -> BARRA, bebidas -> MOZO, lo demas -> COCINA."""
    nombre = _sin_acentos(nombre_categoria)
    if any(nombre.startswith(p) for p in _TRAGOS):
        return BARRA
    if any(nombre.startswith(p) for p in _BEBIDAS):
        return MOZO
    return COCINA


def destino_de_producto(destino_propio, nombre_categoria):
    """El destino de un producto: el propio si lo tiene cargado y es valido; si no, el de su categoria."""
    return destino_valido(destino_propio) or destino_por_categoria(nombre_categoria)


def destinos_presentes(destinos_de_items):
    """Los destinos distintos de una lista (en el orden fijo cocina, barra, mozo)."""
    presentes = set(destinos_de_items)
    return [d for d in DESTINOS if d in presentes]


def estado_inicial(destino, retenida):
    """Estado con el que nace el pedido de un destino. Retenida (primera ronda de una mesa grupal) espera el OK de todos; si no,
    cocina y barra empiezan `pendiente` y las bebidas del mozo ya estan `listo` para llevar."""
    if retenida:
        return RETENIDA
    return LISTO if destino == MOZO else PENDIENTE


def estado_al_liberar(destino):
    """Estado al que pasa un pedido retenido cuando sale la primera ronda."""
    return estado_inicial(destino, False)


def puede_cancelarse(estados):
    """`estados`: {destino: estado} de lo que sigue sin entregar. Se puede cancelar mientras ni cocina ni barra empezaron a
    preparar (retenida o pendiente) y las bebidas del mozo no se llevaron (retenida o listo). Sin estados no hay nada que cancelar."""
    if not estados:
        return False
    for destino, estado in estados.items():
        permitidos = (RETENIDA, LISTO) if destino == MOZO else (RETENIDA, PENDIENTE)
        if estado not in permitidos:
            return False
    return True


def estado_resumen(estados):
    """Un solo estado para toda la comanda: el del destino mas atrasado (None si ya no queda nada sin entregar)."""
    valores = [e for e in estados.values() if e in ORDEN_ESTADOS]
    if not valores:
        return None
    return min(valores, key=ORDEN_ESTADOS.index)


def estado_para_cancelar(estados):
    """Lo que ve la regla de cancelacion: 'retenida' si todo esta retenido, 'pendiente' si todavia se puede cancelar, y si no el
    estado resumen (proceso o listo: ya empezo). None si no queda nada sin entregar."""
    if not estados:
        return None
    if all(e == RETENIDA for e in estados.values()):
        return RETENIDA
    if puede_cancelarse(estados):
        return PENDIENTE
    return estado_resumen(estados) if estado_resumen(estados) not in (RETENIDA, PENDIENTE) else PROCESO


def items_de_destino(items, destino):
    """`items`: lista de (destino, dato). Los datos del destino pedido, en el mismo orden."""
    return [dato for d, dato in items if d == destino]
