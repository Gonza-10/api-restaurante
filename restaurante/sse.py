"""Flujo de eventos del menu (Server-Sent Events).

El servidor empuja al navegador un evento `catalogo` con la version del menu cada vez que cambia, para que un
plato agotado desaparezca de la pantalla del cliente sin refrescarla.

Decisiones de robustez:
- BASADO EN ESTADO, no en eventos: al conectar (y en cada reconexion) se manda la version actual. Si el cliente
  se perdio algun cambio, la version no coincide con la que tenia y vuelve a pedir el menu. Nada se pierde.
- El aviso de Redis (pub/sub) solo DESPIERTA al flujo para ser instantaneo; la version se relee igual cada
  segundo, asi un aviso perdido se corrige en <= 1 s.
- Latido (`: ping`) cada 15 s: mantiene viva la conexion y permite detectar clientes caidos para liberar su lugar.
- Vida maxima por conexion (5 min): el servidor la cierra y el navegador reconecta solo. Evita conexiones zombi.
- Tope de conexiones simultaneas (total y por IP): cada una ocupa un hilo del servidor. Pasado el tope se
  responde 503 y el front usa GET /catalogo/version como respaldo.
- Si Redis falla, el flujo termina limpio y el navegador reintenta (`retry`); nunca queda colgado.
"""
import json
import logging
import threading
import time

logger = logging.getLogger(__name__)

REINTENTO_MS = 2000       # espera del navegador antes de reconectar
LATIDO_SEG = 15           # latido si no hubo cambios
VIDA_MAXIMA_SEG = 300     # el servidor cierra y el navegador reconecta
ESPERA_SEG = 1.0          # cada cuanto se relee la version aunque no haya aviso
MAX_CONEXIONES = 300      # tope total (cada una ocupa un hilo)
MAX_POR_IP = 60           # tope por IP (varios dispositivos pueden compartir red)


def formatear_version(version):
    """Un evento SSE con la version del menu (el id permite que el navegador informe el ultimo recibido)."""
    return f'id: {version}\nevent: catalogo\ndata: {json.dumps({"version": version})}\n\n'


class RegistroConexiones:
    """Cuenta las conexiones abiertas (total y por IP). Es seguro entre hilos."""

    def __init__(self, maximo_total=MAX_CONEXIONES, maximo_por_ip=MAX_POR_IP):
        self._maximo_total = maximo_total
        self._maximo_por_ip = maximo_por_ip
        self._candado = threading.Lock()
        self._total = 0
        self._por_ip = {}

    def tomar(self, ip):
        with self._candado:
            if self._total >= self._maximo_total or self._por_ip.get(ip, 0) >= self._maximo_por_ip:
                return False
            self._total += 1
            self._por_ip[ip] = self._por_ip.get(ip, 0) + 1
            return True

    def soltar(self, ip):
        with self._candado:
            if self._por_ip.get(ip, 0) > 0:
                self._por_ip[ip] -= 1
                if self._por_ip[ip] == 0:
                    del self._por_ip[ip]
                self._total = max(0, self._total - 1)

    @property
    def abiertas(self):
        with self._candado:
            return self._total


class CanalRedis:
    """Conexion propia de UN flujo con Redis: la suscripcion al canal de cambios y la lectura de la version.
    No comparte conexiones con el resto del servidor: abrir una conexion nueva en mitad de un aviso (por ejemplo
    porque el pool estaba ocupado) lo demoraria; asi todas se abren al conectar el cliente, nunca despues.
    esperar() vuelve apenas llega un aviso o al cumplirse el timeout."""

    def __init__(self, crear_cliente, canal, clave_version):
        self._cliente = crear_cliente()
        self._clave_version = clave_version
        self._pubsub = self._cliente.pubsub(ignore_subscribe_messages=True)
        self._pubsub.subscribe(canal)
        self._cliente.get(clave_version)  # abre ya la conexion de lectura

    def esperar(self, segundos):
        self._pubsub.get_message(timeout=segundos)

    def version(self):
        return int(self._cliente.get(self._clave_version) or 0)

    def cerrar(self):
        for recurso in (self._pubsub, self._cliente):
            try:
                recurso.close()
            except Exception:
                pass


class FlujoEventos:
    """Iterador que entrega la respuesta SSE. Django llama a close() cuando termina o se corta la conexion;
    close() libera el lugar aunque el flujo no haya llegado a empezar (un generador solo no lo garantiza)."""

    def __init__(self, canal, ip, registro, reloj=time.monotonic,
                 vida_maxima=VIDA_MAXIMA_SEG, latido=LATIDO_SEG, espera=ESPERA_SEG):
        self._ip = ip
        self._registro = registro
        self._reloj = reloj
        self._vida_maxima = vida_maxima
        self._latido = latido
        self._espera = espera
        self._canal = canal  # ya abierto: si Redis no responde, la vista contesta 503 antes de empezar el flujo
        self._liberado = False
        self._candado = threading.Lock()
        self._generador = self._generar()

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._generador)

    def close(self):
        self._generador.close()
        self._liberar()

    def _liberar(self):
        with self._candado:
            if self._liberado:
                return
            self._liberado = True
        if self._canal is not None:
            self._canal.cerrar()
        self._registro.soltar(self._ip)

    def _generar(self):
        try:
            yield f'retry: {REINTENTO_MS}\n\n'

            ultima = self._canal.version()
            yield formatear_version(ultima)  # siempre se informa la version actual al conectar

            inicio = ultimo_envio = self._reloj()
            while self._reloj() - inicio < self._vida_maxima:
                self._canal.esperar(self._espera)   # vuelve al instante si hay aviso
                actual = self._canal.version()       # la version es la fuente de verdad
                ahora = self._reloj()
                if actual != ultima:
                    ultima = actual
                    ultimo_envio = ahora
                    yield formatear_version(actual)
                elif ahora - ultimo_envio >= self._latido:
                    ultimo_envio = ahora
                    yield ': ping\n\n'
        except GeneratorExit:
            raise
        except Exception:
            # Redis caido o conexion rota: se termina limpio y el navegador reintenta solo
            logger.exception('Flujo de eventos del catalogo interrumpido')
        finally:
            self._liberar()
