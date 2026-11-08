"""Worker de Mercado Pago: confirma los cobros pendientes sin que nadie tenga que preguntar.

Uso (PowerShell, en la raiz del proyecto, con el entorno virtual activo):
    python restaurante/worker_mercadopago.py

Cada MP_SYNC_INTERVALO_SEG segundos (15 por defecto) consulta a Mercado Pago por cada pago `Pendiente` y:
- si se aprobo, lo marca Aprobado y lo anota en la caja (ingreso Venta y, si hay, Propina con la etiqueta MercadoPago);
- si el link vencio sin pagos en curso, lo marca Expirado y libera el saldo de la cuenta.
Los pagos Cancelados o Expirados de las ultimas horas se vuelven a mirar cada 5 minutos por si el cliente pago tarde.
Un error con un pago (o con la base, o con Mercado Pago) se registra y el worker sigue: el proceso no se cae.
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

from restaurante.mercadopago import modo, pasarela
from restaurante.models import Pago
from restaurante.pagos_mp import pagos_a_revisar, sincronizar_pago

INTERVALO_SEGUNDOS = max(5, int(config('MP_SYNC_INTERVALO_SEG', default=15)))
REVISION_TARDIA_SEGUNDOS = 300   # cancelados o vencidos: se vuelven a mirar cada 5 minutos

_ultima_revision_tardia = {}     # id del pago -> instante de la ultima consulta


def ciclo(gateway=None):
    """Una pasada. Devuelve cuantos segundos esperar hasta la proxima."""
    close_old_connections()   # en un proceso largo la conexion a la base puede vencerse entre pasadas
    try:
        ids = pagos_a_revisar()
        gateway = gateway or pasarela()
    except Exception as error:
        print(f'[ERROR] Mercado Pago: no se pudo leer la lista de pagos: {error!r}')
        return INTERVALO_SEGUNDOS
    ahora = time.monotonic()
    pendientes = set(Pago.objects.filter(pk__in=ids, estado='Pendiente').values_list('id', flat=True)) if ids else set()
    for pago_id in ids:
        if pago_id not in pendientes:
            if ahora - _ultima_revision_tardia.get(pago_id, 0) < REVISION_TARDIA_SEGUNDOS:
                continue
            _ultima_revision_tardia[pago_id] = ahora
        try:
            antes = Pago.objects.values_list('estado', flat=True).get(pk=pago_id)
            pago = sincronizar_pago(pago_id, gateway)
            if pago.estado != antes:
                print(f'[MP] Pago {pago_id}: {antes} -> {pago.estado}.')
        except Exception as error:   # un pago con problemas no frena a los demas
            print(f'[ERROR] Mercado Pago: pago {pago_id}: {error!r}')
    return INTERVALO_SEGUNDOS


def main():
    print(f'Worker de Mercado Pago (modo {modo()}): confirma cobros cada {INTERVALO_SEGUNDOS} s. Ctrl+C para salir.')
    try:
        while True:
            time.sleep(ciclo())
    except KeyboardInterrupt:
        print('Worker de Mercado Pago detenido.')


if __name__ == '__main__':
    main()
