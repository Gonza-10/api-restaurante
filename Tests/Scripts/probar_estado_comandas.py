"""Prueba de restaurante/estado_comandas.py (cambios atomicos del estado de una comanda) con un Redis de mentira: no necesita
Redis, Django ni internet. Comprueba la regla; la atomicidad real (WATCH) se prueba con Redis en el Postman.

Uso (desde la raiz del repo):  python Tests/Scripts/probar_estado_comandas.py
"""
import os
import sys
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)


class WatchError(Exception):
    pass


class FakePipe:
    def __init__(self, redis):
        self.redis, self.cola, self.vigilada, self.version = redis, None, None, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def watch(self, clave):
        self.vigilada, self.version = clave, self.redis.versiones.get(clave, 0)

    def unwatch(self):
        self.vigilada = None

    def get(self, clave):
        return self.redis.datos.get(clave)

    def multi(self):
        self.cola = []

    def set(self, clave, valor):
        self.cola.append(('set', clave, valor))

    def delete(self, clave):
        self.cola.append(('delete', clave))

    def execute(self):
        if self.vigilada and self.redis.versiones.get(self.vigilada, 0) != self.version:
            raise WatchError()
        for op in self.cola:
            if op[0] == 'set':
                self.redis.set(op[1], op[2])
            else:
                self.redis.datos.pop(op[1], None)
                self.redis.versiones[op[1]] = self.redis.versiones.get(op[1], 0) + 1


class FakeRedis:
    def __init__(self, *a, **k):
        self.datos, self.versiones, self.interferir = {}, {}, None

    def get(self, clave):
        return self.datos.get(clave)

    def set(self, clave, valor):
        self.datos[clave] = valor
        self.versiones[clave] = self.versiones.get(clave, 0) + 1

    def pipeline(self):
        pipe = FakePipe(self)
        original_multi = pipe.multi

        def multi():
            if self.interferir:           # alguien cambia la clave entre la lectura y la escritura
                self.interferir()
                self.interferir = None
            original_multi()
        pipe.multi = multi
        return pipe


redis_falso = types.ModuleType('redis')
redis_falso.WatchError, redis_falso.Redis = WatchError, FakeRedis
decouple_falso = types.ModuleType('decouple')
decouple_falso.config = lambda nombre, default=None, cast=None: default
sys.modules['redis'], sys.modules['decouple'] = redis_falso, decouple_falso

from restaurante import estado_comandas as ec  # noqa: E402

total = 0
fallos = []


def comprobar(nombre, condicion):
    global total
    total += 1
    if not condicion:
        fallos.append(nombre)
        print(f'  FALLA: {nombre}')


r = ec.redis_client
u = 'aaaaaaaa-0000-0000-0000-000000000001'

# cancelar solo desde retenida o pendiente
r.set(ec.clave_de(u), 'pendiente')
comprobar('pendiente se cancela (borra la clave)', ec.transicionar(u, ('retenida', 'pendiente'), None) == (True, 'pendiente'))
comprobar('ya no tiene estado', ec.estado_de(u) is None)
comprobar('sin clave no cambia', ec.transicionar(u, ('retenida', 'pendiente'), None) == (False, None))

r.set(ec.clave_de(u), 'proceso')
comprobar('en proceso no se cancela', ec.transicionar(u, ('retenida', 'pendiente'), None) == (False, 'proceso'))
comprobar('en proceso sigue igual', ec.estado_de(u) == 'proceso')

# liberar: retenida -> pendiente, y solo esa
r.set(ec.clave_de(u), 'retenida')
comprobar('retenida pasa a pendiente', ec.transicionar(u, ('retenida',), 'pendiente') == (True, 'retenida'))
comprobar('queda pendiente', ec.estado_de(u) == 'pendiente')
comprobar('liberar de nuevo no hace nada', ec.transicionar(u, ('retenida',), 'pendiente') == (False, 'pendiente'))

# la cocina no mueve una retenida
r.set(ec.clave_de(u), 'retenida')
comprobar('cocina no mueve retenida', ec.transicionar(u, ('pendiente', 'proceso', 'listo'), 'proceso') == (False, 'retenida'))
comprobar('retenida sigue retenida', ec.estado_de(u) == 'retenida')

# la cocina avanza y entrega
r.set(ec.clave_de(u), 'pendiente')
comprobar('pendiente a proceso', ec.transicionar(u, ('pendiente', 'proceso', 'listo'), 'proceso')[0])
comprobar('proceso a listo', ec.transicionar(u, ('pendiente', 'proceso', 'listo'), 'listo')[0])
comprobar('listo a entregado (borra)', ec.transicionar(u, ('pendiente', 'proceso', 'listo'), None)[0] and ec.estado_de(u) is None)

# carrera: la cocina la pasa a proceso justo mientras se intenta cancelar -> se reintenta y NO se cancela
r.set(ec.clave_de(u), 'pendiente')
r.interferir = lambda: r.set(ec.clave_de(u), 'proceso')
resultado = ec.transicionar(u, ('retenida', 'pendiente'), None)
comprobar('carrera: gana la cocina, no se cancela', resultado == (False, 'proceso') and ec.estado_de(u) == 'proceso')

print(f'{total - len(fallos)} de {total} chequeos correctos.')
sys.exit(1 if fallos else 0)
