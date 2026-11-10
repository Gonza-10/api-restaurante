"""Prueba del rechazo de una comanda por falta de stock (la carrera por la ultima porcion), de punta a punta.

Por que un script y no Postman: para que dos comandas compitan por lo ultimo hay que saltear el aviso previo del
carrito y mandarlas directo a la cola de RabbitMQ, y Postman no puede publicar en RabbitMQ.

Necesita (todo corriendo): runserver (8080), worker.py, RabbitMQ y Redis, y los scripts SQL 08 a 12 ejecutados.
Usa pika y python-decouple (ya estan en el entorno virtual del proyecto).

Uso (PowerShell, en la raiz del proyecto, con el entorno virtual activo):
    python Tests\\Scripts\\probar_rechazo_comanda.py
    python Tests\\Scripts\\probar_rechazo_comanda.py --base http://127.0.0.1:8080/api/v1

Que comprueba:
  1. Hay stock para UNA sola porcion y se encolan DOS comandas de una porcion: la que llega primero se acepta
     y la segunda se rechaza (no queda nada a medias).
  2. El cliente ve la rechazada con un mensaje generico (sin decir que insumo falta) y sin platos.
  3. El personal (Gerente) ve el motivo interno: que plato y que insumo limito.
  4. La rechazada no aparece en el tablero de Cocina; la aceptada si.
  5. El stock se descontó una sola vez (libro consistente).
  6. Si RabbitMQ reentrega las mismas comandas, no pasa nada (no se duplican ni se descuentan de nuevo).
Todo lo que crea se llama "ZZ Rechazo ..." y se limpia al final (la jornada y la mesa 3 quedan cerradas).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

ARGS = None
RESULTADOS = []


def llamar(metodo, ruta, cuerpo=None, token=None):
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
        return codigo, json.loads(texto) if texto else None
    except ValueError:
        return codigo, texto[:300]


def chequear(nombre, condicion, detalle=''):
    RESULTADOS.append(bool(condicion))
    print(f"  [{'OK' if condicion else 'FALLA'}] {nombre}" + (f'  -> {detalle}' if detalle else ''))


def login(usuario):
    codigo, datos = llamar('POST', '/login', {'usuario': usuario, 'contrasena': ARGS.clave})
    if codigo != 200:
        print(f'No se pudo iniciar sesion con {usuario} ({codigo}): {datos}')
        sys.exit(2)
    return datos['token']


def publicar(payload):
    """Mete la comanda directo en la cola, igual que lo hace la API, pero sin el aviso previo de stock."""
    import pika
    from decouple import config
    conexion = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost', credentials=pika.PlainCredentials(config('RABBIT_USER'), config('RABBIT_PASS'))
    ))
    canal = conexion.channel()
    canal.queue_declare(queue='comandas_pendientes', durable=True)
    canal.basic_publish(exchange='', routing_key='comandas_pendientes', body=json.dumps(payload),
                        properties=pika.BasicProperties(delivery_mode=2))
    conexion.close()


def historial(numero_mesa, pin):
    return llamar('POST', '/mesa/historial', {'numero_mesa': numero_mesa, 'pin': pin})[1]['comandas']


def esperar(condicion, segundos=20):
    """Espera (hasta `segundos`) a que el worker haya procesado lo encolado."""
    limite = time.time() + segundos
    while time.time() < limite:
        valor = condicion()
        if valor:
            return valor
        time.sleep(0.5)
    return condicion()


def main():
    global ARGS
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8080/api/v1')
    parser.add_argument('--usuario', default='lmartinez')
    parser.add_argument('--clave', default='1234')
    ARGS = parser.parse_args()
    ARGS.base = ARGS.base.rstrip('/')
    sufijo = str(int(time.time()))

    print('0. Preparacion: logins y datos de prueba')
    ger = login(ARGS.usuario)
    mozo = login('jperez')
    cocina = login('cruiz')
    llamar('POST', '/jornada/cerrar', token=ger)  # si habia una abierta, se cierra
    for s in llamar('GET', '/sesiones-mesa?estado=Abierto&mesa=3', token=ger)[1]:
        llamar('POST', f"/sesiones-mesa/{s['id']}/cerrar", token=mozo)

    turnos = llamar('GET', '/turnos')[1]
    turno = next((t for t in turnos if t['nombre'] == 'Cena'), turnos[0])
    codigo, jornada = llamar('POST', '/jornada/abrir', {'turno': turno['id']}, token=ger)
    chequear('Se abre la jornada', codigo == 201, jornada if codigo != 201 else '')

    _, prov = llamar('POST', '/proveedores', {'nombre': f'ZZ Rechazo Proveedor {sufijo}'}, token=ger)
    _, insumo = llamar('POST', '/insumos', {'nombre': f'ZZ Rechazo Harina {sufijo}', 'tipo_medida': 'Masa', 'stock_objetivo': 1000}, token=ger)
    # justo para UNA porcion
    llamar('POST', '/compras', {'proveedor': prov['id'], 'lineas': [{'insumo': insumo['id'], 'cantidad': 250, 'costo_total': 500}]}, token=ger)
    _, receta = llamar('POST', '/recetas', {'nombre': f'ZZ Rechazo Receta {sufijo}', 'ingredientes': [{'insumo': insumo['id'], 'cantidad': 250}]}, token=ger)
    categoria = llamar('GET', '/categorias')[1][0]['id']
    nombre_plato = f'ZZ Rechazo Plato {sufijo}'
    _, producto = llamar('POST', '/productos', {'nombre': nombre_plato, 'precio': '4000.00', 'categoria': categoria}, token=ger)
    llamar('PUT', f"/productos/{producto['id']}/receta", {'receta': receta['id']}, token=ger)
    codigo, sesion = llamar('POST', '/sesiones-mesa/abrir', {'numero_mesa': 3, 'cantidad_comensales': 2}, token=mozo)
    chequear('Se abre la mesa 3', codigo == 201, sesion if codigo != 201 else '')
    if codigo != 201:
        sys.exit(2)
    pin = sesion['codigo_pin']

    print('1. Dos comandas de una porcion compiten por la ultima (se saltea el aviso previo del carrito)')
    uuid_a, uuid_b = str(uuid.uuid4()), str(uuid.uuid4())
    for uid in (uuid_a, uuid_b):
        publicar({'id_comanda_uuid': uid, 'id_pedido_cabecera': sesion['id'], 'items': [{'id': producto['id'], 'precio': None}]})

    def buscar(lista, uid):
        return next((c for c in lista if c['id_comanda_uuid'].lower() == uid.lower()), None)

    esperar(lambda: len(historial(3, pin)) >= 2)
    comandas = historial(3, pin)
    a, b = buscar(comandas, uuid_a), buscar(comandas, uuid_b)
    chequear('El worker proceso las dos (si falla: worker.py apagado)', a is not None and b is not None)
    if a is None or b is None:
        sys.exit(2)
    chequear('La primera se acepta (pendiente, 1 plato)', a['estado'] == 'pendiente' and a['items'][0]['cantidad'] == 1, a['estado'])
    chequear('La segunda se rechaza', b['estado'] == 'rechazada', b['estado'])

    print('2. Lo que ve el cliente')
    mensaje = f'Insumos insuficientes. Por ahora no podemos preparar {nombre_plato}. Disculpe las molestias.'
    chequear('Mensaje generico con el nombre del plato', b['mensaje'] == mensaje, b['mensaje'])
    chequear('No dice que insumo falta', 'harina' not in (b['mensaje'] or '').lower())
    chequear('La rechazada no trae platos ni suma al total', b['items'] == [] and float(b['total']) == 0)
    chequear('La aceptada no trae mensaje', a['mensaje'] is None)

    print('3. Lo que ve el personal')
    rechazadas = llamar('GET', '/comandas-rechazadas', token=ger)[1]
    r = buscar(rechazadas, uuid_b)
    chequear('El Gerente la ve entre las rechazadas', r is not None)
    chequear('Con el motivo interno: plato, cuantas alcanzan y que insumo limito',
             r is not None and nombre_plato in r['motivo'] and 'alcanzan 0' in r['motivo'] and 'Harina' in r['motivo'],
             r['motivo'] if r else '')
    chequear('Cocina NO ve las rechazadas (403)', llamar('GET', '/comandas-rechazadas', token=cocina)[0] == 403)

    print('4. Tablero de Cocina')
    tablero = llamar('GET', '/cocina/tablero', token=cocina)[1]
    chequear('La aceptada esta en el tablero', buscar(tablero, uuid_a) is not None)
    chequear('La rechazada NO esta en el tablero', buscar(tablero, uuid_b) is None)

    print('5. Stock')
    _, ins = llamar('GET', f"/insumos/{insumo['id']}", token=ger)
    chequear('La harina quedo en cero (se descontó una sola vez)', float(ins['stock_actual']) == 0, ins['stock_actual'])
    _, movs = llamar('GET', f"/movimientos-stock?insumo={insumo['id']}&tipo=consumo", token=ger)
    chequear('Un solo movimiento de consumo, de -250', len(movs) == 1 and float(movs[0]['cantidad']) == -250,
             [m['cantidad'] for m in movs])
    chequear('El libro es consistente', llamar('GET', '/stock/verificacion', token=ger)[1]['consistente'] is True)

    print('6. RabbitMQ reentrega las mismas comandas (idempotencia)')
    for uid in (uuid_a, uuid_b):
        publicar({'id_comanda_uuid': uid, 'id_pedido_cabecera': sesion['id'], 'items': [{'id': producto['id'], 'precio': None}]})
    time.sleep(3)
    comandas = historial(3, pin)
    chequear('Siguen siendo 2 comandas (no se duplicaron)', len(comandas) == 2, len(comandas))
    _, movs = llamar('GET', f"/movimientos-stock?insumo={insumo['id']}&tipo=consumo", token=ger)
    chequear('El stock no se descontó de nuevo', len(movs) == 1)
    chequear('La rechazada sigue rechazada', buscar(comandas, uuid_b)['estado'] == 'rechazada')

    print('7. Limpieza')
    llamar('POST', '/jornada/cerrar', token=ger)
    llamar('POST', f"/sesiones-mesa/{sesion['id']}/cerrar", token=mozo)
    llamar('PATCH', f"/productos/{producto['id']}", {'activo': False}, token=ger)
    llamar('PUT', f"/productos/{producto['id']}/receta", {'receta': None}, token=ger)
    codigo = llamar('DELETE', f"/recetas/{receta['id']}", token=ger)[0]
    chequear('Se borra la receta de prueba', codigo == 204, codigo)
    llamar('DELETE', f"/insumos/{insumo['id']}", token=ger)
    llamar('DELETE', f"/proveedores/{prov['id']}", token=ger)
    chequear('El libro termina consistente', llamar('GET', '/stock/verificacion', token=ger)[1]['consistente'] is True)

    ok = sum(RESULTADOS)
    print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
    sys.exit(0 if ok == len(RESULTADOS) else 1)


if __name__ == '__main__':
    main()
