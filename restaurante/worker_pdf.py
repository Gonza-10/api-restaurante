import os
import sys
import json
import django
import pika
import uuid
from decouple import config
from fpdf import FPDF

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from restaurante.models import ComandaRecibida

CARPETA_TICKETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tickets')
os.makedirs(CARPETA_TICKETS, exist_ok=True)


from django.db import connection


def generar_pdf_ticket(uuid_comanda: str):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT cr.Id, cr.FechaHoraRecepcion, m.Numero
            FROM ComandaRecibida cr
            INNER JOIN PedidoCabecera pc ON pc.Id = cr.IdPedidoCabecera
            INNER JOIN Mesa m ON m.Id = pc.IdMesa
            WHERE cr.IdComandaUuid = '{uuid_comanda}'
            """
        )
        fila = cursor.fetchone()

    if fila is None:
        raise ComandaRecibida.DoesNotExist(f'Comanda {uuid_comanda} no encontrada')

    id_comanda_recibida, fecha_hora_recepcion, numero_mesa = fila

    comanda = ComandaRecibida.objects.select_related('pedido_cabecera').get(id=id_comanda_recibida)
    detalles = comanda.pedido_cabecera.detalles.select_related('producto').all()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Savage Grill - Comprobante', ln=True, align='C')
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, f'Mesa: {numero_mesa}', ln=True)
    pdf.cell(0, 8, f'Comanda: {uuid_comanda}', ln=True)
    pdf.cell(0, 8, f'Fecha: {fecha_hora_recepcion.strftime("%d/%m/%Y %H:%M")}', ln=True)
    pdf.ln(5)

    total = 0
    for d in detalles:
        pdf.cell(0, 8, f'{d.cantidad}x {d.producto.nombre} - ${d.sub_total}', ln=True)
        total += float(d.sub_total)

    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, f'Total: ${total:.2f}', ln=True)

    ruta = os.path.join(CARPETA_TICKETS, f'{uuid_comanda}.pdf')
    pdf.output(ruta)
    return ruta


def procesar_evento(ch, method, properties, body):
    datos = json.loads(body)
    uuid_comanda = datos['id_comanda_uuid']
    try:
        ruta = generar_pdf_ticket(uuid_comanda)
        print(f'[OK] PDF generado para comanda {uuid_comanda} -> {ruta}')
    except ComandaRecibida.DoesNotExist:
        print(f'[ERROR] Comanda {uuid_comanda} no encontrada, no se genero PDF.')
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    parametros = pika.ConnectionParameters(
        host='localhost',
        credentials=pika.PlainCredentials(
            config('RABBIT_USER'), config('RABBIT_PASS')
        )
    )
    conexion = pika.BlockingConnection(parametros)
    canal = conexion.channel()
    canal.queue_declare(queue='comandas_listas', durable=True)
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(queue='comandas_listas', on_message_callback=procesar_evento)

    print('Worker PDF escuchando comandas_listas. Ctrl+C para salir.')
    canal.start_consuming()


if __name__ == '__main__':
    main()