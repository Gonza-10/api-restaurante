"""Worker de la cotizacion oficial: consulta al BCRA cada 30 minutos y guarda lo que cambio.

Uso (PowerShell, en la raiz del proyecto, con el entorno virtual activo):
    python restaurante/worker_cotizacion.py

Si el BCRA no responde se mantiene la ultima cotizacion guardada y se reintenta a los 5 minutos. El proceso no se cae
por un error de red ni de base de datos: lo registra y sigue.
"""
import os
import sys
import time

import django
from decouple import config

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import close_old_connections

from restaurante.cotizacion import BcraNoDisponible, actualizar_cotizaciones

INTERVALO_SEGUNDOS = int(config('COTIZACION_INTERVALO_SEG', default=1800))   # 30 minutos
REINTENTO_SEGUNDOS = min(300, INTERVALO_SEGUNDOS)                            # tras un error, a los 5 minutos


def ciclo():
    """Una consulta. Devuelve cuantos segundos esperar hasta la proxima."""
    close_old_connections()   # en un proceso largo la conexion a la base puede vencerse entre consultas
    try:
        resultado = actualizar_cotizaciones()
        guardadas = ', '.join(resultado['guardadas']) or 'ninguna'
        sin_cambios = ', '.join(resultado['sin_cambios']) or 'ninguna'
        print(f'[COTIZACION] Consulta correcta. Guardadas: {guardadas}. Sin cambios: {sin_cambios}.')
        return INTERVALO_SEGUNDOS
    except BcraNoDisponible as error:
        print(f'[COTIZACION] No se pudo actualizar: {error} Sigue vigente la ultima guardada; reintento en {REINTENTO_SEGUNDOS // 60} min.')
    except Exception as error:   # por ejemplo, la base no responde: el worker no se cae
        print(f'[ERROR] Fallo inesperado al actualizar la cotizacion: {error!r}. Reintento en {REINTENTO_SEGUNDOS // 60} min.')
    return REINTENTO_SEGUNDOS


def main():
    print(f'Worker de cotizacion: consulta al BCRA cada {INTERVALO_SEGUNDOS // 60} minutos. Ctrl+C para salir.')
    try:
        while True:
            time.sleep(ciclo())
    except KeyboardInterrupt:
        print('Worker de cotizacion detenido.')


if __name__ == '__main__':
    main()
