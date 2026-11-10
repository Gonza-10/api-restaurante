"""Pruebas de la carga de fotos de productos (restaurante/imagenes_carga.py). No necesitan Django, base de datos ni internet.

Uso (desde la raiz del repo):  python Tests/Scripts/probar_imagenes_carga.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from restaurante.imagenes_carga import clave_nombre, leer_filas, nombre_en_zip, planificar  # noqa: E402

total = 0
fallos = []


def comprobar(nombre, condicion):
    global total
    total += 1
    if not condicion:
        fallos.append(nombre)
        print(f'  FALLA: {nombre}')


H1 = 'a' * 32
H2 = 'b' * 32

# ---------- nombres ----------
comprobar('sin acentos ni mayusculas', clave_nombre('  Ensalada  CÉSAR ') == 'ensalada cesar')
comprobar('nombre vacio', clave_nombre(None) == '')

# ---------- CSV ----------
filas, errores = leer_filas(f'﻿1;Coca-Cola 1L;/media/productos/{H1}.png\n\n2;Agua Mineral 500 ml;/media/productos/{H2}.jpg\n')
comprobar('lee dos filas (con BOM y linea en blanco)', len(filas) == 2 and not errores)
comprobar('trae id, nombre y ruta', filas[0] == (1, 'Coca-Cola 1L', f'/media/productos/{H1}.png'))
filas, errores = leer_filas(f'1;Algo;/media/productos/{H1}.gif\n2;Otro\n3;;/media/productos/{H1}.png\nx;Bien;/media/productos/{H2}.webp\n')
comprobar('una ruta con extension rara es un error', any('Algo' in e for e in errores))
comprobar('columnas de menos es un error', any('3 columnas' in e for e in errores))
comprobar('falta el nombre es un error', any('falta el nombre' in e for e in errores))
comprobar('un id que no es numero no frena la fila', filas == [(None, 'Bien', f'/media/productos/{H2}.webp')])
filas, errores = leer_filas('1;Ruta;/media/productos/../../etc/passwd\n')
comprobar('una ruta que sale de la carpeta se rechaza', not filas and len(errores) == 1)

# ---------- miembros del zip ----------
comprobar('miembro con media/', nombre_en_zip(f'media/productos/{H1}.jpg') == f'{H1}.jpg')
comprobar('miembro sin media/', nombre_en_zip(f'productos/{H1}.png') == f'{H1}.png')
comprobar('miembro con ..', nombre_en_zip(f'media/productos/../{H1}.jpg') is None)
comprobar('miembro de otra carpeta', nombre_en_zip(f'otra/{H1}.jpg') is None)
comprobar('la carpeta sola', nombre_en_zip('media/productos/') is None)
comprobar('nombre que no es de 32 hex', nombre_en_zip('media/productos/foto.jpg') is None)

# ---------- plan ----------
ruta1, ruta2, ruta3 = (f'/media/productos/{c * 32}.jpg' for c in 'abc')
filas = [(1, 'Coca-Cola 1L', ruta1), (2, 'ensalada cesar', ruta2), (3, 'Producto Fantasma', ruta3)]
productos = [(10, 'Coca-Cola 1L', None), (11, 'Ensalada César', ''), (12, 'Otro', None)]
plan = planificar(filas, productos)
comprobar('asigna por nombre aunque el id no coincida', plan['asignar'] == [(10, 'Coca-Cola 1L', ruta1), (11, 'Ensalada César', ruta2)])
comprobar('avisa del que no existe', plan['sin_producto'] == ['Producto Fantasma'])
plan = planificar(filas[:1], [(10, 'Coca-Cola 1L', '/media/productos/x.jpg')])
comprobar('no pisa una foto existente', plan['asignar'] == [] and plan['ya_tienen'] == ['Coca-Cola 1L'])
plan = planificar(filas[:1], [(10, 'Coca-Cola 1L', '/media/productos/x.jpg')], pisar=True)
comprobar('con pisar la reemplaza', plan['asignar'] == [(10, 'Coca-Cola 1L', ruta1)])
plan = planificar(filas[:1], [(10, 'Coca-Cola 1L', None), (13, 'coca-cola 1l', None)])
comprobar('dos productos con el mismo nombre: no se adivina', plan['asignar'] == [] and plan['ambiguos'] == ['Coca-Cola 1L'])
plan = planificar([(1, 'Coca-Cola 1L', ruta1), (9, 'Coca-Cola 1L', ruta2)], [(10, 'Coca-Cola 1L', None)])
comprobar('el CSV repite el producto: la primera foto se asigna y la repetida queda como ambigua',
          plan['asignar'] == [(10, 'Coca-Cola 1L', ruta1)] and plan['ambiguos'] == ['Coca-Cola 1L'])
comprobar('repetir la corrida con todo cargado no cambia nada',
          planificar(filas[:1], [(10, 'Coca-Cola 1L', ruta1)])['asignar'] == [])

# ---------- los archivos reales de Gonza (si estan al lado) ----------
csv_real = os.path.join(RAIZ, 'Productos_Imagenes_SavageGrill.csv')
if os.path.exists(csv_real):
    with open(csv_real, encoding='utf-8-sig') as f:
        filas, errores = leer_filas(f.read())
    comprobar('el CSV real tiene 35 filas validas', len(filas) == 35 and not errores)

print(f'{total - len(fallos)} de {total} chequeos correctos.')
sys.exit(1 if fallos else 0)
