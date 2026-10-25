"""Prueba de punta a punta del aviso en tiempo real del menu (Server-Sent Events).

Que comprueba:
  1. Al conectarse a /catalogo/eventos llega la version actual del menu.
  2. Cuando Cocina agota un plato, el evento llega en menos de 1,5 s y el plato sale del menu.
  3. Al reactivarlo, llega otro evento y el plato vuelve al menu.
  4. Un cliente que estuvo desconectado durante un cambio se entera igual al reconectarse (no se pierde nada).
  5. Editar un producto (precio y descripcion) con la jornada abierta tambien llega en tiempo real y se ve en el menu.
  6. (opcional, --latido) el servidor manda latidos para mantener viva la conexion.

Requisitos: el servidor corriendo (runserver 8080) y Redis activo. Solo usa la libreria estandar de Python.
Uso (PowerShell, con el venv activo, en la raiz del repo):
    python Tests\\Scripts\\probar_sse.py
    python Tests\\Scripts\\probar_sse.py --latido        # tarda ~17 s mas
    python Tests\\Scripts\\probar_sse.py --base http://127.0.0.1:8080/api/v1 --usuario cruiz --gerente lmartinez --clave 1234
"""
import argparse
import http.client
import json
import sys
import threading
import time
from urllib.parse import urlparse

PASARON, FALLARON = [], []


def chequear(nombre, condicion, detalle=''):
    (PASARON if condicion else FALLARON).append(nombre)
    print(f"  [{'OK ' if condicion else 'FALLA'}] {nombre}" + (f'  ({detalle})' if detalle else ''))
    return condicion


class Api:
    def __init__(self, base):
        u = urlparse(base)
        self.host, self.puerto, self.prefijo = u.hostname, u.port or 80, u.path.rstrip('/')
        self.token = None

    def pedir(self, metodo, ruta, cuerpo=None):
        con = http.client.HTTPConnection(self.host, self.puerto, timeout=15)
        cabeceras = {'Content-Type': 'application/json'}
        if self.token:
            cabeceras['Authorization'] = f'Bearer {self.token}'
        con.request(metodo, self.prefijo + ruta, json.dumps(cuerpo) if cuerpo is not None else None, cabeceras)
        r = con.getresponse()
        datos = r.read()
        con.close()
        try:
            return r.status, json.loads(datos) if datos else None
        except ValueError:
            return r.status, datos


class Escucha(threading.Thread):
    """Mantiene abierta la conexion SSE y anota cada linea con la hora a la que llego."""

    def __init__(self, api, ultimo_id=None):
        super().__init__(daemon=True)
        self.api, self.ultimo_id = api, ultimo_id
        self.lineas, self.eventos, self.status = [], [], None
        self._con = None
        self._cierra = threading.Event()
        self.conectado = threading.Event()

    def run(self):
        try:
            self._con = http.client.HTTPConnection(self.api.host, self.api.puerto, timeout=25)
            cabeceras = {'Accept': 'text/event-stream'}
            if self.ultimo_id is not None:
                cabeceras['Last-Event-ID'] = str(self.ultimo_id)
            self._con.request('GET', self.api.prefijo + '/catalogo/eventos', headers=cabeceras)
            resp = self._con.getresponse()
            self.status = resp.status
            self.conectado.set()
            nombre = None
            while not self._cierra.is_set():
                linea = resp.fp.readline()
                if not linea:
                    break
                linea = linea.decode('utf-8').rstrip('\r\n')
                self.lineas.append((time.monotonic(), linea))
                if linea.startswith('event:'):
                    nombre = linea[6:].strip()
                elif linea.startswith('data:') and nombre == 'catalogo':
                    self.eventos.append((time.monotonic(), json.loads(linea[5:])['version']))
                    nombre = None
        except Exception:
            pass
        finally:
            self.conectado.set()

    def esperar_version(self, distinta_de, segundos=5.0, desde=0.0):
        """Espera un evento llegado despues de `desde` con una version distinta de `distinta_de`."""
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            for t, v in self.eventos:
                if t >= desde and v != distinta_de:
                    return t, v
            time.sleep(0.02)
        return None, None

    def cerrar(self):
        self._cierra.set()
        try:
            self._con.close()
        except Exception:
            pass


def menu(api):
    estado, datos = api.pedir('GET', '/productos')
    return {p['id']: p for p in datos} if estado == 200 else {}


def accion(api, escucha, metodo, ruta, cuerpo, distinta_de):
    """Hace un cambio y espera el evento. Devuelve (status, version nueva, ms del pedido, ms hasta el evento
    contados desde que el servidor respondio; negativo = el evento llego antes que la respuesta)."""
    t0 = time.monotonic()
    estado, datos = api.pedir(metodo, ruta, cuerpo)
    t1 = time.monotonic()
    t_evento, version = escucha.esperar_version(distinta_de=distinta_de, segundos=5, desde=t0)
    espera = (t_evento - t1) * 1000 if t_evento else None
    return estado, datos, version, (t1 - t0) * 1000, espera


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8080/api/v1')  # 127.0.0.1: en Windows 'localhost' puede sumar ~2 s por conexion
    ap.add_argument('--usuario', default='cruiz', help='usuario de Cocina')
    ap.add_argument('--gerente', default='lmartinez', help='usuario Admin o Gerente (para editar productos)')
    ap.add_argument('--clave', default='1234')
    ap.add_argument('--latido', action='store_true', help='tambien espera un latido (~17 s)')
    args = ap.parse_args()

    cocina = Api(args.base)
    gestion = Api(args.base)
    for api, usuario in ((cocina, args.usuario), (gestion, args.gerente)):
        estado, datos = api.pedir('POST', '/login', {'usuario': usuario, 'contrasena': args.clave})
        if estado != 200:
            sys.exit(f'No se pudo iniciar sesion como {usuario} ({estado}): {datos}')
        api.token = datos['token']
    publico = Api(args.base)  # el cliente no tiene token

    productos = menu(publico)
    if not productos:
        sys.exit('No hay productos en el menu para probar.')
    id_producto = next(iter(productos))
    original = productos[id_producto]
    print(f"Producto de prueba: {original['nombre']} (id {id_producto})")

    escucha = escucha2 = None
    agotado = False
    editado = False
    try:
        print('\n1) Conexion y version inicial')
        escucha = Escucha(publico)
        escucha.start()
        escucha.conectado.wait(5)
        chequear('Responde 200', escucha.status == 200, f'status {escucha.status}')
        t, v0 = escucha.esperar_version(distinta_de=None, segundos=3)
        chequear('Al conectar llega la version actual', v0 is not None, f'version {v0}')
        chequear('Manda el tiempo de reintento (retry)', any(l.startswith('retry:') for _, l in escucha.lineas))

        print('\n2) Cocina agota el plato: el cliente conectado se entera solo')
        estado, _, v1, ms_pedido, espera = accion(cocina, escucha, 'POST', f'/productos/{id_producto}/agotar', None, v0)
        agotado = estado == 200
        chequear('Agotar responde 200', agotado, f'status {estado}, el pedido tardo {ms_pedido:.0f} ms')
        chequear('Llega un evento con otra version', v1 is not None and v1 != v0, f'{v0} -> {v1}')
        if espera is not None:
            chequear('El evento llega a lo sumo 1500 ms despues de que el servidor responde', espera < 1500, f'{espera:.0f} ms')
        chequear('El plato ya no esta en el menu', id_producto not in menu(publico))

        print('\n3) Cocina lo reactiva')
        estado, _, v2, ms_pedido, espera = accion(cocina, escucha, 'POST', f'/productos/{id_producto}/reactivar', None, v1)
        agotado = estado != 200
        chequear('Reactivar responde 200', estado == 200, f'status {estado}, el pedido tardo {ms_pedido:.0f} ms')
        chequear('Llega otro evento', v2 is not None and v2 != v1, f'{v1} -> {v2}')
        if espera is not None:
            chequear('El evento llega a lo sumo 1500 ms despues de que el servidor responde', espera < 1500, f'{espera:.0f} ms')
        chequear('El plato vuelve al menu', id_producto in menu(publico))

        print('\n4) Editar un producto con la jornada abierta tambien se avisa (precio y descripcion)')
        precio_nuevo = f"{float(original['precio']) + 1:.2f}"
        descripcion_nueva = (original.get('descripcion') or '') + ' (prueba en vivo)'
        editado = True
        estado, _, v3, ms_pedido, espera = accion(
            gestion, escucha, 'PATCH', f'/productos/{id_producto}',
            {'precio': precio_nuevo, 'descripcion': descripcion_nueva}, v2)
        chequear('Editar responde 200', estado == 200, f'status {estado}, el pedido tardo {ms_pedido:.0f} ms')
        chequear('Llega un evento con otra version', v3 is not None and v3 != v2, f'{v2} -> {v3}')
        if espera is not None:
            chequear('El evento llega a lo sumo 1500 ms despues de que el servidor responde', espera < 1500, f'{espera:.0f} ms')
        visto = menu(publico).get(id_producto, {})
        chequear('El menu ya muestra el precio nuevo', visto.get('precio') == precio_nuevo, f"{visto.get('precio')}")
        chequear('El menu ya muestra la descripcion nueva', visto.get('descripcion') == descripcion_nueva.strip())
        estado, _, v4, _, _ = accion(
            gestion, escucha, 'PATCH', f'/productos/{id_producto}',
            {'precio': original['precio'], 'descripcion': original.get('descripcion')}, v3)
        editado = estado != 200
        chequear('Se restauran los datos originales y tambien se avisa', estado == 200 and v4 not in (None, v3), f'{v3} -> {v4}')
        visto = menu(publico).get(id_producto, {})
        chequear('El menu vuelve a mostrar el precio original', visto.get('precio') == original['precio'])

        print('\n5) Un cliente desconectado durante un cambio se entera al reconectarse')
        escucha.cerrar()
        time.sleep(0.3)
        estado, _ = cocina.pedir('POST', f'/productos/{id_producto}/agotar')
        agotado = estado == 200
        escucha2 = Escucha(publico, ultimo_id=v4)
        escucha2.start()
        escucha2.conectado.wait(5)
        t, v5 = escucha2.esperar_version(distinta_de=v4, segundos=3)
        chequear('Al reconectar recibe la version nueva (sin esperar otro cambio)', v5 is not None and v5 != v4, f'{v4} -> {v5}')
        estado, _ = cocina.pedir('POST', f'/productos/{id_producto}/reactivar')
        agotado = estado != 200

        print('\n6) Respaldo: GET /catalogo/version')
        estado, datos = publico.pedir('GET', '/catalogo/version')
        chequear('Responde la version actual', estado == 200 and isinstance(datos.get('version'), int), str(datos))

        if args.latido:
            print('\n7) Latido (espera ~17 s)')
            time.sleep(17)
            chequear('Llego al menos un latido', any(l.startswith(': ping') for _, l in escucha2.lineas))
    finally:
        for e in (escucha, escucha2):
            if e:
                e.cerrar()
        if agotado:  # que la prueba nunca deje el plato agotado ni editado
            cocina.pedir('POST', f'/productos/{id_producto}/reactivar')
            print('\n(el plato quedo reactivado)')
        if editado:
            gestion.pedir('PATCH', f'/productos/{id_producto}',
                          {'precio': original['precio'], 'descripcion': original.get('descripcion')})
            print('(el producto quedo con sus datos originales)')

    print(f'\nResultado: {len(PASARON)} correctas, {len(FALLARON)} con falla')
    sys.exit(1 if FALLARON else 0)


if __name__ == '__main__':
    main()
