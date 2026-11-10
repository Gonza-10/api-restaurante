"""Nombres de los tickets de comanda (carpeta `tickets/`), sin base de datos ni Django.

Cada comanda genera un ticket para cocina. Antes se llamaba solo por su UUID; ahora lleva un nombre legible y, al final, el UUID entre
parentesis: 'MESA 2 - Pedido 1 (0a6809bf-7d4d-4429-9e62-e6f85ddc2e3a).pdf'. El 'Pedido N' cuenta las comandas aceptadas de esa
sesion de la mesa, en el orden en que llegaron. El UUID se conserva porque es la clave con la que el front pide el ticket
(`/tickets/<uuid>.pdf`) y asi se lo encuentra sin consultar la base; tambien evita choques entre dos sesiones de la misma mesa."""
import re

_UUID_ARCHIVO = re.compile(r'^(?P<legible>.+?) \((?P<uuid>[0-9a-fA-F-]{36})\)\.pdf$')


def nombre_ticket(numero_mesa, numero_pedido, uuid_comanda):
    """'MESA 2 - Pedido 1 (<uuid>).pdf'."""
    return f'MESA {int(numero_mesa)} - Pedido {int(numero_pedido)} ({str(uuid_comanda).lower()}).pdf'


def buscar_ticket(nombres, uuid_comanda):
    """El archivo del ticket de esa comanda entre los `nombres` de la carpeta, o None. Acepta el nombre nuevo y el viejo (solo el UUID),
    porque los tickets ya generados antes del cambio siguen en la carpeta."""
    uuid_comanda = str(uuid_comanda).lower()
    viejo = f'{uuid_comanda}.pdf'
    sufijo = f' ({uuid_comanda}).pdf'
    for nombre in nombres:
        bajo = nombre.lower()
        if bajo == viejo or (bajo.endswith(sufijo) and _UUID_ARCHIVO.match(nombre)):
            return nombre
    return None


def nombre_descarga(nombre_archivo):
    """El nombre que ve quien baja el ticket: sin el UUID ('MESA 2 - Pedido 1.pdf'). Los tickets viejos conservan su nombre."""
    coincide = _UUID_ARCHIVO.match(nombre_archivo)
    return f"{coincide.group('legible')}.pdf" if coincide else nombre_archivo
