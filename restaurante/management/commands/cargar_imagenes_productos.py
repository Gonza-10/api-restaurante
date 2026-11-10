"""Carga las fotos de los productos desde un zip y un CSV (ver restaurante/imagenes_carga.py para el formato).

Uso (se puede repetir sin problema: lo ya cargado no se toca):
    python manage.py cargar_imagenes_productos fotos.zip imagenes.csv --simular   # solo muestra que haria
    python manage.py cargar_imagenes_productos fotos.zip imagenes.csv             # carga
    python manage.py cargar_imagenes_productos fotos.zip imagenes.csv --pisar     # tambien reemplaza las que ya tienen foto
"""
import os
import zipfile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from restaurante.catalogo import invalidar_cache_catalogo
from restaurante.imagenes_carga import MAX_BYTES, leer_filas, nombre_en_zip, planificar
from restaurante.models import Producto
from restaurante.views import IMAGEN_SUBCARPETA, _detectar_extension_imagen


class Command(BaseCommand):
    help = 'Carga las fotos de los productos desde un zip y un CSV (id;nombre;ruta), buscando cada producto por nombre.'

    def add_arguments(self, parser):
        parser.add_argument('zip', help='Zip con las fotos en media/productos/')
        parser.add_argument('csv', help='CSV sin encabezado, separado por ;  (id;nombre;/media/productos/<hex>.jpg)')
        parser.add_argument('--simular', action='store_true', help='Solo muestra lo que haria, sin tocar nada.')
        parser.add_argument('--pisar', action='store_true', help='Tambien reemplaza la foto de los productos que ya tienen una.')

    def handle(self, *args, **opciones):
        try:
            with open(opciones['csv'], encoding='utf-8-sig') as archivo:
                filas, errores = leer_filas(archivo.read())
            fotos = zipfile.ZipFile(opciones['zip'])
        except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as error:
            raise CommandError(f'No se pudo leer un archivo: {error}')
        for error in errores:
            self.stderr.write(self.style.WARNING(error))

        productos = list(Producto.objects.values_list('id', 'nombre', 'imagen_url'))
        plan = planificar(filas, productos, pisar=opciones['pisar'])
        en_zip = {nombre_en_zip(m): m for m in fotos.namelist() if nombre_en_zip(m)}

        carpeta = os.path.join(settings.MEDIA_ROOT, IMAGEN_SUBCARPETA)
        cargadas = 0
        for id_producto, nombre, ruta in plan['asignar']:
            archivo = os.path.basename(ruta)
            miembro = en_zip.get(archivo)
            if miembro is None:
                self.stderr.write(self.style.WARNING(f'{nombre}: la foto {archivo} no esta en el zip.'))
                continue
            datos = fotos.read(miembro)
            if len(datos) > MAX_BYTES or _detectar_extension_imagen(datos[:16]) != archivo.rsplit('.', 1)[1].replace('jpeg', 'jpg'):
                self.stderr.write(self.style.WARNING(f'{nombre}: {archivo} es muy pesada o no es una imagen valida, se salta.'))
                continue
            if not opciones['simular']:
                os.makedirs(carpeta, exist_ok=True)
                with open(os.path.join(carpeta, archivo), 'wb') as destino:
                    destino.write(datos)
                Producto.objects.filter(pk=id_producto).update(imagen_url=ruta)
            cargadas += 1
            self.stdout.write(f'  {"(simulado) " if opciones["simular"] else ""}{nombre}  <-  {archivo}')

        if cargadas and not opciones['simular']:
            invalidar_cache_catalogo()   # el menu de los clientes se actualiza solo
        self.stdout.write(self.style.SUCCESS(f'{"Se cargarian" if opciones["simular"] else "Cargadas"}: {cargadas} foto(s).'))
        if plan['ya_tienen']:
            self.stdout.write(f'Ya tenian foto (no se tocaron; usar --pisar para reemplazar): {len(plan["ya_tienen"])}')
        for titulo, clave in (('Sin producto con ese nombre en esta base', 'sin_producto'), ('Nombre repetido (no se adivina)', 'ambiguos')):
            if plan[clave]:
                self.stdout.write(self.style.WARNING(f'{titulo}: ' + ', '.join(plan[clave])))
        sin_foto = [n for _, n, img in productos if not img and n not in {x[1] for x in plan['asignar']}]
        if sin_foto:
            self.stdout.write(f'Productos que siguen sin foto: {len(sin_foto)} ({", ".join(sin_foto[:8])}{"..." if len(sin_foto) > 8 else ""})')
