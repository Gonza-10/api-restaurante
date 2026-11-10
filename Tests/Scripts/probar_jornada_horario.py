"""Prueba de apertura y cierre de jornada (entorno limpio y horarios). Solo libreria estandar.

Uso (PowerShell, con el servidor corriendo):
    python Tests\\Scripts\\probar_jornada_horario.py
    python Tests\\Scripts\\probar_jornada_horario.py --base http://127.0.0.1:8080/api/v1

Comprueba, contra una base recien armada con los scripts SQL:
  1. hay turnos y mesas cargados (lo que Gonza dijo que estaba vacio);
  2. abrir con un turno que no existe da 400 limpio (no 500);
  3. abrir un turno de manera explicita funciona a cualquier hora, y avisa si es fuera de su horario;
  4. abrir con el cuerpo vacio nunca da 500 (abre si la hora corresponde a un turno; si no, 400 con la lista);
  5. cerrar devuelve la lista de advertencias.
Al terminar deja la jornada cerrada. Si ya habia una abierta, la CIERRA antes de empezar (usar en pruebas).
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

ARGS = None
RESULTADOS = []


def llamar(metodo, ruta, cuerpo=None, token=None):
    """Devuelve (codigo_http, json_o_texto). No lanza error con 4xx/5xx: queremos ver el codigo."""
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pedido = urllib.request.Request(ARGS.base + ruta, data=datos, method=metodo)
    pedido.add_header('Content-Type', 'application/json')
    if token:
        pedido.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            codigo, texto = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        codigo, texto = e.code, e.read().decode()
    except urllib.error.URLError as e:
        print(f'No se pudo conectar a {ARGS.base}: {e.reason}\n¿Esta corriendo runserver en ese puerto?')
        sys.exit(2)
    try:
        return codigo, json.loads(texto)
    except ValueError:
        return codigo, texto[:300]


def chequear(nombre, condicion, detalle=''):
    RESULTADOS.append(bool(condicion))
    print(f"  [{'OK' if condicion else 'FALLA'}] {nombre}" + (f'  -> {detalle}' if detalle else ''))


def main():
    global ARGS
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8080/api/v1')
    parser.add_argument('--usuario', default='lmartinez')
    parser.add_argument('--clave', default='1234')
    ARGS = parser.parse_args()
    ARGS.base = ARGS.base.rstrip('/')

    print('1. Login del Gerente')
    codigo, datos = llamar('POST', '/login', {'usuario': ARGS.usuario, 'contrasena': ARGS.clave})
    chequear('login 200 con token', codigo == 200 and isinstance(datos, dict) and 'token' in datos, f'HTTP {codigo}')
    if codigo != 200:
        print('Sin token no se puede seguir (¿corrio el seed?).')
        sys.exit(1)
    token = datos['token']

    print('2. Datos base (turnos y mesas)')
    codigo, turnos = llamar('GET', '/turnos')
    lista_turnos = turnos.get('results', turnos) if isinstance(turnos, dict) else turnos
    chequear('GET /turnos devuelve al menos 1 turno', codigo == 200 and len(lista_turnos) >= 1, f'HTTP {codigo}, {len(lista_turnos) if isinstance(lista_turnos, list) else "?"} turnos')
    codigo, mesas = llamar('GET', '/mesas', token=token)
    lista_mesas = mesas.get('results', mesas) if isinstance(mesas, dict) else mesas
    chequear('GET /mesas devuelve al menos 1 mesa', codigo == 200 and len(lista_mesas) >= 1, f'HTTP {codigo}, {len(lista_mesas) if isinstance(lista_mesas, list) else "?"} mesas')
    cena = next((t for t in lista_turnos if t.get('nombre') == 'Cena'), None)
    chequear('existe el turno "Cena"', cena is not None)
    if cena is None:
        sys.exit(1)

    print('3. Estado inicial: cerrar cualquier jornada abierta')
    codigo, _ = llamar('POST', '/jornada/cerrar', token=token)
    chequear('cierre previo (200 si habia una abierta, 409 si no)', codigo in (200, 409), f'HTTP {codigo}')

    print('4. Abrir con un turno que no existe')
    codigo, datos = llamar('POST', '/jornada/abrir', {'turno': 999999}, token)
    chequear('turno inexistente -> 400 (no 500)', codigo == 400, f'HTTP {codigo} {datos}')

    print('5. Abrir la Cena de manera explicita (a la hora que sea)')
    codigo, datos = llamar('POST', '/jornada/abrir', {'turno': cena['id']}, token)
    chequear('abrir con turno explicito -> 201', codigo == 201, f'HTTP {codigo}')
    if codigo == 201:
        chequear('la respuesta trae "advertencias" (lista)', isinstance(datos.get('advertencias'), list))
        print(f"      advertencias: {datos.get('advertencias')}  (vacia si ahora esta dentro del horario de la Cena)")
        codigo, datos = llamar('POST', '/jornada/abrir', {'turno': cena['id']}, token)
        chequear('abrir otra encima -> 409', codigo == 409, f'HTTP {codigo}')
        codigo, datos = llamar('POST', '/jornada/cerrar', token=token)
        chequear('cerrar -> 200 con "advertencias" (lista)', codigo == 200 and isinstance(datos.get('advertencias'), list), f'HTTP {codigo}')
        if codigo == 200:
            print(f"      advertencias: {datos.get('advertencias')}")

    print('6. Abrir con el cuerpo vacio (turno sugerido por la hora)')
    codigo, datos = llamar('POST', '/jornada/abrir', {}, token)
    chequear('cuerpo vacio -> 201 (hora dentro de un turno) o 400 con la lista de turnos, nunca 500',
             codigo in (201, 400), f'HTTP {codigo}')
    if codigo == 400:
        chequear('el 400 trae la lista de turnos', isinstance(datos, dict) and bool(datos.get('turnos')))

    print('7. Limpieza: dejar la jornada cerrada')
    llamar('POST', '/jornada/cerrar', token=token)
    codigo, datos = llamar('GET', '/jornada/actual', token=token)
    print(f'      GET /jornada/actual -> HTTP {codigo}')

    ok = sum(RESULTADOS)
    print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
    sys.exit(0 if ok == len(RESULTADOS) else 1)


if __name__ == '__main__':
    main()
