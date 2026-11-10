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
        self.redis, self.cola, self.vigiladas = redis, None, {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def watch(self, *claves):
        for clave in claves:
            self.vigiladas[clave] = self.redis.versiones.get(clave, 0)

    def unwatch(self):
        self.vigiladas = {}

    def get(self, clave):
        return self.redis.datos.get(clave)

    def multi(self):
        self.cola = []

    def set(self, clave, valor):
        self.cola.append(('set', clave, valor))

    def delete(self, clave):
        self.cola.append(('delete', clave))

    def execute(self):
        if any(self.redis.versiones.get(c, 0) != v for c, v in self.vigiladas.items()):
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

# ---------- varios destinos (cocina, barra, mozo) ----------
v = 'bbbbbbbb-0000-0000-0000-000000000002'
claves = lambda: {d: ec.estado_de(v, d) for d in ('COCINA', 'BARRA', 'MOZO')}
comprobar('claves por destino', ec.clave_de(v) == f'comanda:estado:{v}' and ec.clave_de(v, 'BARRA') == f'comanda:estado:{v}:barra'
          and ec.clave_de(v, 'MOZO') == f'comanda:estado:{v}:mozo')

ec.crear(v, {'COCINA': 'retenida', 'BARRA': 'retenida', 'MOZO': 'retenida'})
comprobar('crear deja una clave por destino', ec.estados_de(v) == {'COCINA': 'retenida', 'BARRA': 'retenida', 'MOZO': 'retenida'})
comprobar('todo retenido: estado global retenida', ec.estado_global(v) == 'retenida' and ec.estado_cancelable(v) == 'retenida')
comprobar('liberar cambia cada destino a su estado de salida', ec.liberar(v) is True)
comprobar('cocina y barra pendiente, mozo listo', claves() == {'COCINA': 'pendiente', 'BARRA': 'pendiente', 'MOZO': 'listo'})
comprobar('liberar de nuevo no hace nada', ec.liberar(v) is False)
comprobar('el estado global es el mas atrasado', ec.estado_global(v) == 'pendiente')
comprobar('se puede cancelar', ec.estado_cancelable(v) == 'pendiente')

# la barra empieza el trago: ya no se puede cancelar nada (y no se toca ningun destino)
ec.transicionar(v, ('pendiente',), 'proceso', destino='BARRA')
comprobar('barra en proceso: global sigue pendiente (cocina)', ec.estado_global(v) == 'pendiente')
comprobar('barra en proceso: ya no se cancela', ec.estado_cancelable(v) == 'proceso')
comprobar('cancelar_todo no hace nada', ec.cancelar_todo(v) is False and claves() == {'COCINA': 'pendiente', 'BARRA': 'proceso', 'MOZO': 'listo'})

# la cocina y la barra avanzan por su cuenta
comprobar('cocina listo', ec.transicionar(v, ('pendiente',), 'proceso')[0] and ec.transicionar(v, ('proceso',), 'listo')[0])
comprobar('el mozo no confirma lo que no esta listo', ec.transicionar(v, ('listo',), None, destino='BARRA') == (False, 'proceso'))
comprobar('el mozo confirma sus bebidas', ec.transicionar(v, ('listo',), None, destino='MOZO') == (True, 'listo'))
comprobar('quedan cocina y barra', ec.estados_de(v) == {'COCINA': 'listo', 'BARRA': 'proceso'})
comprobar('entregar_todo deja la comanda cerrada', ec.entregar_todo(v) is True and ec.estados_de(v) == {} and ec.estado_global(v) is None)
comprobar('entregar_todo sin nada no cambia', ec.entregar_todo(v) is False)

# cancelar con todo sin empezar: se borran todas las claves juntas; las bebidas listas del mozo no lo impiden
ec.crear(v, {'COCINA': 'pendiente', 'MOZO': 'listo'})
comprobar('cancelar_todo borra todo', ec.cancelar_todo(v) is True and ec.estados_de(v) == {})
ec.crear(v, {'BARRA': 'retenida'})
comprobar('retenida se cancela', ec.cancelar_todo(v) is True and ec.estados_de(v) == {})

# carrera: la barra empieza justo mientras se cancela -> se reevalua y NO se cancela
ec.crear(v, {'COCINA': 'pendiente', 'BARRA': 'pendiente'})
r.interferir = lambda: r.set(ec.clave_de(v, 'BARRA'), 'proceso')
comprobar('carrera: gana la barra, no se cancela', ec.cancelar_todo(v) is False and claves()['BARRA'] == 'proceso' and claves()['COCINA'] == 'pendiente')

print(f'{total - len(fallos)} de {total} chequeos correctos.')
sys.exit(1 if fallos else 0)
