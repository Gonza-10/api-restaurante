"""Reglas puras de la carga masiva de fotos de productos (sin Django ni base, para poder probarlas solas).

La carga usa dos archivos que arma quien prepara el menu:
- un CSV sin encabezado, separado por `;`, con una fila por producto:  id;nombre;/media/productos/<32 hex>.<jpg|png|webp>
- un zip con las fotos en `media/productos/`.
El producto se busca por NOMBRE (el id del CSV puede no coincidir con el de esta base): sin acentos ni mayusculas.
"""
import csv
import io
import re
import unicodedata

RUTA_FOTO = re.compile(r'^/media/productos/[0-9a-f]{32}\.(jpg|png|webp)$')   # la misma que acepta la API de productos
_MIEMBRO_ZIP = re.compile(r'^(?:media/)?productos/([0-9a-f]{32}\.(?:jpg|png|webp))$')
MAX_BYTES = 2 * 1024 * 1024   # el mismo limite que la API de productos


def clave_nombre(texto):
    """El nombre sin acentos, mayusculas ni espacios de mas, para comparar."""
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    sin_acentos = ''.join(c for c in descompuesto if not unicodedata.combining(c))
    return ' '.join(sin_acentos.casefold().split())


def leer_filas(texto):
    """Filas del CSV como (id o None, nombre, ruta). Devuelve (filas, errores): una fila mal armada no frena a las demas."""
    filas, errores = [], []
    lector = csv.reader(io.StringIO(texto.lstrip('﻿')), delimiter=';')
    for numero, fila in enumerate(lector, start=1):
        if not fila or not any(c.strip() for c in fila):
            continue
        if len(fila) != 3:
            errores.append(f'Fila {numero}: se esperaban 3 columnas (id;nombre;ruta) y hay {len(fila)}.')
            continue
        id_texto, nombre, ruta = (c.strip() for c in fila)
        if not nombre:
            errores.append(f'Fila {numero}: falta el nombre.')
        elif not RUTA_FOTO.match(ruta):
            errores.append(f'Fila {numero} ({nombre}): la ruta no es /media/productos/<32 hex>.jpg|png|webp.')
        else:
            filas.append((int(id_texto) if id_texto.isdigit() else None, nombre, ruta))
    return filas, errores


def nombre_en_zip(miembro):
    """El nombre de archivo de un miembro del zip si es una foto valida de media/productos/ (si no, None: protege de rutas raras)."""
    coincide = _MIEMBRO_ZIP.match(miembro or '')
    return coincide.group(1) if coincide else None


def planificar(filas, productos, pisar=False):
    """Que producto recibe que foto. `productos`: [(id, nombre, imagen_url actual)].
    Devuelve {'asignar': [(id_producto, nombre, ruta)], 'sin_producto': [nombre], 'ya_tienen': [nombre], 'ambiguos': [nombre]}.
    Un producto que ya tiene foto no se toca salvo `pisar`; dos productos con el mismo nombre no se tocan (ambiguo)."""
    por_nombre = {}
    for id_producto, nombre, imagen in productos:
        por_nombre.setdefault(clave_nombre(nombre), []).append((id_producto, nombre, imagen))
    plan = {'asignar': [], 'sin_producto': [], 'ya_tienen': [], 'ambiguos': []}
    usados = set()
    for _, nombre, ruta in filas:
        candidatos = por_nombre.get(clave_nombre(nombre), [])
        if not candidatos:
            plan['sin_producto'].append(nombre)
        elif len(candidatos) > 1:
            plan['ambiguos'].append(nombre)
        else:
            id_producto, nombre_real, imagen = candidatos[0]
            if id_producto in usados:
                plan['ambiguos'].append(nombre)   # el CSV repite el producto: no se adivina cual foto vale
            elif imagen and not pisar:
                plan['ya_tienen'].append(nombre_real)
            else:
                usados.add(id_producto)
                plan['asignar'].append((id_producto, nombre_real, ruta))
    return plan
