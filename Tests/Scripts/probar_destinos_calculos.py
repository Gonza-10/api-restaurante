"""Pruebas de los destinos de un pedido (restaurante/destinos_calculos.py). No necesitan Django, base de datos ni internet.

Uso (desde la raiz del repo):  python Tests/Scripts/probar_destinos_calculos.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from restaurante.destinos_calculos import (  # noqa: E402
    destino_de_producto, destino_por_categoria, destino_valido, destinos_presentes, estado_al_liberar, estado_inicial,
    estado_para_cancelar, estado_resumen, items_de_destino, puede_cancelarse,
)

total = 0
fallos = []


def comprobar(nombre, condicion):
    global total
    total += 1
    if not condicion:
        fallos.append(nombre)
        print(f'  FALLA: {nombre}')


# ---------- destino por categoria ----------
comprobar('Tragos -> barra', destino_por_categoria('Tragos') == 'BARRA')
comprobar('Coctel con acento -> barra', destino_por_categoria('Cócteles') == 'BARRA')
comprobar('Bebidas -> mozo', destino_por_categoria('Bebidas') == 'MOZO')
comprobar('mayusculas y espacios', destino_por_categoria('  BEBIDAS ') == 'MOZO')
comprobar('Principales -> cocina', destino_por_categoria('Principales') == 'COCINA')
comprobar('Postres -> cocina', destino_por_categoria('Postres') == 'COCINA')
comprobar('categoria vacia -> cocina', destino_por_categoria(None) == 'COCINA' and destino_por_categoria('') == 'COCINA')
comprobar('una categoria que contiene la palabra pero no empieza igual no cuenta', destino_por_categoria('Tabla de tragos') == 'COCINA')

# ---------- destino propio gana ----------
comprobar('sin destino propio: el de la categoria', destino_de_producto(None, 'Tragos') == 'BARRA')
comprobar('destino propio gana', destino_de_producto('COCINA', 'Tragos') == 'COCINA')
comprobar('destino propio en minusculas', destino_de_producto('mozo', 'Principales') == 'MOZO')
comprobar('destino propio invalido se ignora', destino_de_producto('COCINERO', 'Bebidas') == 'MOZO')
comprobar('destino propio vacio se ignora', destino_de_producto('  ', 'Tragos') == 'BARRA')
comprobar('destino_valido', destino_valido(' barra ') == 'BARRA' and destino_valido('x') is None and destino_valido(None) is None)

# ---------- destinos de una comanda ----------
comprobar('destinos presentes en orden fijo', destinos_presentes(['MOZO', 'COCINA', 'MOZO', 'BARRA']) == ['COCINA', 'BARRA', 'MOZO'])
comprobar('solo cocina', destinos_presentes(['COCINA', 'COCINA']) == ['COCINA'])
comprobar('sin items', destinos_presentes([]) == [])
items = [('COCINA', 'hamburguesa'), ('BARRA', 'mojito'), ('COCINA', 'papas'), ('MOZO', 'agua')]
comprobar('items de cocina', items_de_destino(items, 'COCINA') == ['hamburguesa', 'papas'])
comprobar('items de barra', items_de_destino(items, 'BARRA') == ['mojito'])
comprobar('items de un destino sin nada', items_de_destino(items[:1], 'MOZO') == [])

# ---------- estados de salida ----------
comprobar('retenida en cualquier destino', all(estado_inicial(d, True) == 'retenida' for d in ('COCINA', 'BARRA', 'MOZO')))
comprobar('cocina y barra nacen pendiente', estado_inicial('COCINA', False) == 'pendiente' and estado_inicial('BARRA', False) == 'pendiente')
comprobar('las bebidas del mozo nacen listas', estado_inicial('MOZO', False) == 'listo')
comprobar('al liberar', estado_al_liberar('COCINA') == 'pendiente' and estado_al_liberar('MOZO') == 'listo')

# ---------- cancelar ----------
comprobar('nada que cancelar', not puede_cancelarse({}))
comprobar('cocina pendiente se cancela', puede_cancelarse({'COCINA': 'pendiente'}))
comprobar('todo retenido se cancela', puede_cancelarse({'COCINA': 'retenida', 'BARRA': 'retenida', 'MOZO': 'retenida'}))
comprobar('bebidas listas del mozo no impiden cancelar', puede_cancelarse({'COCINA': 'pendiente', 'MOZO': 'listo'}))
comprobar('cocina en proceso no se cancela', not puede_cancelarse({'COCINA': 'proceso'}))
comprobar('barra en proceso no se cancela', not puede_cancelarse({'COCINA': 'pendiente', 'BARRA': 'proceso'}))
comprobar('barra lista no se cancela', not puede_cancelarse({'BARRA': 'listo'}))
comprobar('solo bebidas listas se cancelan', puede_cancelarse({'MOZO': 'listo'}))

# ---------- estado de toda la comanda ----------
comprobar('resumen: el mas atrasado', estado_resumen({'COCINA': 'listo', 'BARRA': 'pendiente'}) == 'pendiente')
comprobar('resumen: proceso antes que listo', estado_resumen({'COCINA': 'listo', 'BARRA': 'proceso'}) == 'proceso')
comprobar('resumen: retenida primero', estado_resumen({'COCINA': 'retenida', 'MOZO': 'retenida'}) == 'retenida')
comprobar('resumen vacio', estado_resumen({}) is None)
comprobar('para cancelar: nada', estado_para_cancelar({}) is None)
comprobar('para cancelar: todo retenido', estado_para_cancelar({'COCINA': 'retenida', 'MOZO': 'retenida'}) == 'retenida')
comprobar('para cancelar: pendiente', estado_para_cancelar({'COCINA': 'pendiente', 'MOZO': 'listo'}) == 'pendiente')
comprobar('para cancelar: barra empezo (cocina pendiente) cuenta como proceso',
          estado_para_cancelar({'COCINA': 'pendiente', 'BARRA': 'proceso'}) == 'proceso')
comprobar('para cancelar: cocina lista', estado_para_cancelar({'COCINA': 'listo'}) == 'listo')

print(f'{total - len(fallos)} de {total} chequeos correctos.')
sys.exit(1 if fallos else 0)
