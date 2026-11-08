"""Prueba de los nombres de los tickets de comanda (carpeta `tickets/`): 'MESA 2 - Pedido 1 (<uuid>).pdf', como se los encuentra por
UUID (tambien a los viejos, que se llaman solo por el UUID) y el nombre que ve quien los baja. Sin base de datos ni Django.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_ticket_calculos.py
"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('ticket_calculos', Path(__file__).resolve().parents[2] / 'restaurante' / 'ticket_calculos.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

U1 = '0a6809bf-7d4d-4429-9e62-e6f85ddc2e3a'
U2 = '1db34738-0785-4037-a7f2-fabb258407b1'
total = 0
fallos = []


def ok(nombre, condicion):
    global total
    total += 1
    print(('OK   ' if condicion else 'FALLA'), nombre)
    if not condicion:
        fallos.append(nombre)


ok('nombre del ticket', t.nombre_ticket(2, 1, U1) == f'MESA 2 - Pedido 1 ({U1}).pdf')
ok('el segundo pedido de la misma mesa', t.nombre_ticket(2, 2, U2) == f'MESA 2 - Pedido 2 ({U2}).pdf')
ok('el UUID siempre va en minuscula', t.nombre_ticket(2, 1, U1.upper()) == t.nombre_ticket(2, 1, U1))
ok('acepta el UUID como objeto', t.nombre_ticket(2, 1, __import__('uuid').UUID(U1)) == t.nombre_ticket(2, 1, U1))
carpeta = [t.nombre_ticket(2, 1, U1), t.nombre_ticket(2, 2, U2), f'{U2[:-1]}9.pdf', 'David - 08-11-26 (factura 7).pdf', 'notas.txt']
ok('se encuentra por UUID', t.buscar_ticket(carpeta, U1) == f'MESA 2 - Pedido 1 ({U1}).pdf')
ok('se encuentra aunque el front pida el UUID en mayuscula', t.buscar_ticket(carpeta, U2.upper()) == f'MESA 2 - Pedido 2 ({U2}).pdf')
ok('un UUID que no esta no se encuentra', t.buscar_ticket(carpeta, '99999999-9999-4999-8999-999999999999') is None)
ok('carpeta vacia', t.buscar_ticket([], U1) is None)
ok('tambien se encuentra el ticket viejo (solo el UUID)', t.buscar_ticket([f'{U1}.pdf'], U1) == f'{U1}.pdf')
ok('el UUID parecido pero distinto no se confunde', t.buscar_ticket([f'{U2[:-1]}9.pdf'], U2) is None)
ok('una factura no se confunde con un ticket', t.buscar_ticket(['David - 08-11-26 (factura 7).pdf'], U1) is None)
ok('el nombre de descarga no lleva el UUID', t.nombre_descarga(t.nombre_ticket(2, 1, U1)) == 'MESA 2 - Pedido 1.pdf')
ok('el ticket viejo conserva su nombre', t.nombre_descarga(f'{U1}.pdf') == f'{U1}.pdf')
ok('numero de mesa y de pedido de dos cifras', t.nombre_ticket(12, 10, U1) == f'MESA 12 - Pedido 10 ({U1}).pdf')

print(f'\n{total - len(fallos)}/{total} chequeos OK')
sys.exit(1 if fallos else 0)
