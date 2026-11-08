"""Cobro con Mercado Pago (hito 4): iniciar, confirmar, cancelar y vencer.

Flujo (Checkout Pro con preferencias; el cliente paga solo, redirigido a Mercado Pago):
1. El cliente pide pagar: se emite la factura si no habia (necesita caja abierta y consumo) y se crea un Pago `Pendiente`
   que RESERVA ese monto del saldo. Recien despues (fuera de los bloqueos de la base) se crea el link en Mercado Pago.
   Solo hay un pago pendiente por factura.
2. Se consulta a Mercado Pago por la referencia `SG-<id del pago>` (el worker cada pocos segundos y a demanda cuando el
   cliente o el mozo preguntan). Cuando hay un pago `approved` por el monto exacto (cuenta + propina) el Pago pasa a
   `Aprobado` y la caja anota un ingreso `Venta` y otro `Propina` con la etiqueta MercadoPago.
3. Un rechazo no termina el cobro: el cliente puede reintentar con el mismo link. Termina cuando se aprueba, cuando vence
   el link (`Expirado`) o cuando se cancela (`Cancelado`).

Reglas de seguridad:
- Nunca se marca `Expirado` ni `Cancelado` sin que el link de Mercado Pago haya vencido de verdad (la fecha de expiracion paso
  o Mercado Pago confirmo el vencimiento) y sin pagos en curso.
- Una aprobacion tardia (el pago ya estaba `Expirado` o `Cancelado`) igual se registra: la plata entro.
- Si Mercado Pago informa un monto distinto al esperado, NO se aprueba solo: queda anotado en el historial para revisarlo.
- El monto que se registra es el bruto; la comision (neto) queda solo como dato informativo.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .caja import MEDIO_MERCADO_PAGO, caja_abierta, caja_abierta_bloqueada, registrar_movimiento
from .cobros_calculos import CERO, CobroInvalido, MONEDA_BASE
from .cuenta import (
    ReglaCuenta, _actualizar_factura, _evento, _metodo, _pagos_como_dicts, comandas_en_cocina, emitir_factura, factura_vigente,
    total_de_sesion,
)
from .cuenta_calculos import saldo_de_la_cuenta
from .mercadopago import MercadoPagoError, pasarela, resolver_estado, vencimiento
from .models import Factura, Pago

METODO = 'MercadoPago'
MARGEN_EXPIRACION = timedelta(minutes=2)       # despues de vencer el link se espera un poco antes de dar el pago por perdido
VENTANA_APROBACION_TARDIA = timedelta(hours=3)


def referencia_de(pago):
    return f'SG-{pago.id}'


def _es_mp(pago):
    return pago.metodo_pago.nombre == METODO


# ---------- iniciar ----------

def iniciar_pago(sesion, monto_cuenta=None, propina=CERO, clave=None, gateway=None):
    """El cliente (o quien sea) empieza a pagar con Mercado Pago. `monto_cuenta` y `propina` en pesos; sin `monto_cuenta`
    se paga todo el saldo. Devuelve (pago, creado). Si ya hay un pago pendiente lo devuelve tal cual (`creado=False`):
    asi un reintento o un doble toque no genera dos links."""
    gateway = gateway or pasarela()
    # Antes de emitir la factura (que congela la mesa y frena los pedidos) se descarta lo que se sabe que va a fallar:
    # un cliente que toca "pagar" por error o antes de tiempo no tiene que dejar la mesa trabada.
    if propina < 0:
        raise CobroInvalido('La propina no puede ser negativa.')
    if monto_cuenta is not None and monto_cuenta <= 0:
        raise CobroInvalido('El monto de la cuenta a pagar debe ser mayor a cero.')
    en_cocina = comandas_en_cocina(sesion)
    if en_cocina:
        raise ReglaCuenta('Todavia hay pedidos en preparacion: se paga cuando la mesa tenga todo lo pedido.',
                          comandas_en_cocina=en_cocina)
    if monto_cuenta is not None and factura_vigente(sesion) is None and monto_cuenta > total_de_sesion(sesion):
        raise CobroInvalido(f'El monto a pagar ({monto_cuenta}) supera el total de la cuenta ({total_de_sesion(sesion)}).')
    factura, _ = emitir_factura(sesion.id, None)   # ReglaCuenta si no hay caja abierta, consumo o la mesa esta cerrada

    with transaction.atomic():
        factura = Factura.objects.select_for_update().get(pk=factura.pk)
        if clave:
            previo = Pago.objects.filter(clave_idempotencia=clave).first()
            if previo is not None:
                if previo.factura_id != factura.id:
                    raise ReglaCuenta('Esa clave de operacion ya se uso en otra cuenta.')
                return previo, False
        if factura.estado != 'Emitida':
            raise ReglaCuenta('La cuenta ya esta pagada.' if factura.estado == 'Pagada' else 'La factura esta anulada.')
        pendiente = Pago.objects.filter(factura=factura, estado='Pendiente').select_related('metodo_pago').first()
        if pendiente is not None:
            return pendiente, False
        if caja_abierta() is None:
            raise ReglaCuenta('No hay una caja abierta. Un Admin o Gerente debe abrirla antes de cobrar.')
        en_cocina = comandas_en_cocina(sesion)
        if en_cocina:
            raise ReglaCuenta('Todavia hay pedidos en preparacion: se paga cuando la mesa tenga todo lo pedido.',
                              comandas_en_cocina=en_cocina)

        saldo = saldo_de_la_cuenta(factura.total, _pagos_como_dicts(factura))
        if saldo <= 0:
            raise ReglaCuenta('La cuenta ya esta cubierta: no queda saldo para cobrar.')
        monto = saldo if monto_cuenta is None else monto_cuenta
        if monto <= 0:
            raise CobroInvalido('El monto de la cuenta a pagar debe ser mayor a cero.')
        if monto > saldo:
            raise CobroInvalido(f'El monto a pagar ({monto}) supera el saldo de la cuenta ({saldo}).')
        if propina < 0:
            raise CobroInvalido('La propina no puede ser negativa.')

        expira = vencimiento()
        pago = Pago.objects.create(
            factura=factura, metodo_pago=_metodo(METODO), monto=monto, fecha_hora=timezone.now(), estado='Pendiente',
            moneda=MONEDA_BASE, monto_recibido=monto + propina, cotizacion=1, monto_propina=propina, vuelto=CERO,
            empleado=None, empleado_propina=sesion.empleado if propina > 0 else None,
            clave_idempotencia=clave or None, fecha_hora_expiracion=expira,
        )
        Pago.objects.filter(pk=pago.pk).update(referencia_externa=referencia_de(pago))
        pago.referencia_externa = referencia_de(pago)
        _evento(pago, 'Cobro iniciado', None, 'Pendiente', None,
                f'Mercado Pago: cuenta {monto} + propina {propina}. Vence {expira:%d/%m %H:%M}.')
        mesa = sesion.mesa.numero

    # fuera de los bloqueos: la llamada de red puede tardar y no debe frenar la caja ni la factura
    try:
        pref = gateway.crear_preferencia(referencia_de(pago), f'Cuenta mesa {mesa} - Savage Grill', monto, propina, expira)
    except MercadoPagoError as error:
        with transaction.atomic():
            Pago.objects.filter(pk=pago.pk).update(estado='Cancelado')
            _evento(pago, 'No se pudo crear el link', 'Pendiente', 'Cancelado', None, str(error))
        raise ReglaCuenta('No se pudo conectar con Mercado Pago. Probar de nuevo en un momento o pagar de otra forma.',
                          estado=502) from error
    Pago.objects.filter(pk=pago.pk).update(mp_preferencia_id=pref['id'], mp_url_pago=pref['url'])
    pago.mp_preferencia_id, pago.mp_url_pago = pref['id'], pref['url']
    return pago, True


# ---------- confirmar ----------

def _aprobar(pago_id, datos, tardia):
    """Pasa el pago a Aprobado y anota el ingreso en la caja. Devuelve True si quedo aprobado."""
    with transaction.atomic():
        factura_id = Pago.objects.get(pk=pago_id).factura_id
        factura = Factura.objects.select_for_update().get(pk=factura_id)
        pago = Pago.objects.get(pk=pago_id)   # leido con la factura ya bloqueada: dos sincronizaciones a la vez no aprueban dos veces
        if pago.estado == 'Aprobado':
            return True
        if Pago.objects.filter(mp_pago_id=datos['id']).exclude(pk=pago.pk).exists():
            return False   # ese pago de Mercado Pago ya esta registrado en otro cobro
        esperado = pago.monto + pago.monto_propina
        if datos['monto'] is None or datos['monto'] != esperado:
            if pago.mp_estado != 'monto-distinto':
                Pago.objects.filter(pk=pago.pk).update(mp_estado='monto-distinto')
                _evento(pago, 'Monto distinto', pago.estado, pago.estado, None,
                        f"Mercado Pago informa {datos['monto']} y se esperaban {esperado}. No se aprueba solo: revisar.")
            return False
        caja = caja_abierta_bloqueada()
        if caja is None:
            raise ReglaCuenta('No hay una caja abierta para registrar el cobro de Mercado Pago.')

        anterior = pago.estado
        Pago.objects.filter(pk=pago.pk).update(
            estado='Aprobado', mp_pago_id=datos['id'], mp_estado='approved', mp_monto_neto=datos['neto'],
            fecha_hora=timezone.now())
        detalle = f"Mercado Pago {datos['id']}: acreditado {datos['monto']}" + (f", neto {datos['neto']}" if datos['neto'] else '')
        _evento(pago, 'Aprobacion tardia' if tardia else 'Aprobado', anterior, 'Aprobado', None, detalle)

        mesa = factura.pedido_cabecera.mesa.numero
        registrar_movimiento(caja, 'Ingreso', 'Venta', MONEDA_BASE, pago.monto, None, pago=pago, medio=MEDIO_MERCADO_PAGO,
                             descripcion=f'Cobro con Mercado Pago de la mesa {mesa}')
        if pago.monto_propina > 0:
            registrar_movimiento(caja, 'Ingreso', 'Propina', MONEDA_BASE, pago.monto_propina, None, pago=pago,
                                 medio=MEDIO_MERCADO_PAGO, descripcion=f'Propina con Mercado Pago de la mesa {mesa}')
        _actualizar_factura(factura)
    return True


def _marcar_final(pago_id, estado, evento, detalle, empleado=None):
    with transaction.atomic():
        factura_id = Pago.objects.get(pk=pago_id).factura_id
        Factura.objects.select_for_update().get(pk=factura_id)
        pago = Pago.objects.get(pk=pago_id)
        if pago.estado != 'Pendiente':
            return pago
        Pago.objects.filter(pk=pago.pk, estado='Pendiente').update(estado=estado)
        _evento(pago, evento, 'Pendiente', estado, empleado, detalle)
    return Pago.objects.select_related('metodo_pago').get(pk=pago_id)


def sincronizar_pago(pago_id, gateway=None, ahora=None):
    """Pregunta a Mercado Pago como va el cobro y actualiza lo que haga falta. Devuelve el pago ya actualizado.
    Un pago `Cancelado` o `Expirado` de las ultimas horas tambien se mira, por si se aprobo tarde."""
    gateway = gateway or pasarela()
    ahora = ahora or timezone.now()
    pago = Pago.objects.select_related('metodo_pago').get(pk=pago_id)
    if not _es_mp(pago):
        raise ReglaCuenta('Ese pago no es de Mercado Pago.')
    reciente = pago.fecha_hora_expiracion is not None and ahora - pago.fecha_hora_expiracion < VENTANA_APROBACION_TARDIA
    if pago.estado != 'Pendiente' and not (pago.estado in ('Cancelado', 'Expirado') and reciente):
        return pago

    try:
        pagos_mp = gateway.buscar_pagos(pago.referencia_externa or referencia_de(pago))
    except MercadoPagoError as error:
        raise ReglaCuenta(f'No se pudo consultar a Mercado Pago: {error}', estado=502) from error
    veredicto, dato = resolver_estado(pagos_mp)

    if veredicto == 'aprobado':
        _aprobar(pago.id, dato, tardia=pago.estado != 'Pendiente')
    elif pago.estado == 'Pendiente':
        if dato is not None and dato['estado'] != pago.mp_estado:
            Pago.objects.filter(pk=pago.pk).update(mp_estado=dato['estado'][:30])
            _evento(pago, 'Estado en Mercado Pago', 'Pendiente', 'Pendiente', None, f"{dato['estado']} {dato['detalle']}".strip())
        vencido = pago.fecha_hora_expiracion is not None and ahora > pago.fecha_hora_expiracion + MARGEN_EXPIRACION
        if vencido and veredicto != 'en_curso':
            _marcar_final(pago.id, 'Expirado', 'Vencio el link', 'Paso la fecha de expiracion sin un pago aprobado.')
    return Pago.objects.select_related('metodo_pago').get(pk=pago.pk)


# ---------- cancelar ----------

def cancelar_pago(pago_id, empleado=None, motivo=None, gateway=None):
    """Cancela un cobro pendiente. Primero se confirma con Mercado Pago que no se pago y se vence el link; si no se puede
    confirmar, NO se cancela (el cliente podria pagar despues). Devuelve el pago."""
    gateway = gateway or pasarela()
    pago = sincronizar_pago(pago_id, gateway)   # si justo se aprobo, queda Aprobado
    if pago.estado != 'Pendiente':
        if pago.estado == 'Aprobado':
            raise ReglaCuenta('El pago ya se aprobo: no se puede cancelar.')
        return pago
    try:
        veredicto = resolver_estado(gateway.buscar_pagos(pago.referencia_externa))[0]
        if veredicto == 'en_curso':
            raise ReglaCuenta('Mercado Pago esta procesando un pago de esta cuenta: esperar a que se resuelva.')
        if veredicto == 'aprobado':   # solo llega aca si el monto no coincide (si no, sincronizar_pago ya lo habria aprobado)
            raise ReglaCuenta('Mercado Pago informa un pago aprobado por un monto distinto al de la cuenta: revisarlo en '
                              'Mercado Pago antes de cancelar.')
        if pago.mp_preferencia_id and not gateway.expirar_preferencia(pago.mp_preferencia_id):
            raise ReglaCuenta('Mercado Pago no confirmo que el link quedo vencido: el pago no se cancela todavia.', estado=502)
    except MercadoPagoError as error:
        raise ReglaCuenta(f'No se pudo confirmar con Mercado Pago: {error} El pago no se cancela todavia.', estado=502) from error
    return _marcar_final(pago.id, 'Cancelado', 'Cancelado', (motivo or 'Cancelado por el cliente')[:400], empleado)


# ---------- para el worker ----------

def pagos_a_revisar(ahora=None):
    """Pagos de Mercado Pago que conviene consultar: los pendientes y los cancelados o vencidos hace poco."""
    ahora = ahora or timezone.now()
    desde = ahora - VENTANA_APROBACION_TARDIA
    pendientes = list(Pago.objects.filter(estado='Pendiente', metodo_pago__nombre=METODO).values_list('id', flat=True))
    tardios = list(Pago.objects.filter(estado__in=('Cancelado', 'Expirado'), metodo_pago__nombre=METODO,
                                       fecha_hora_expiracion__gte=desde).values_list('id', flat=True))
    return pendientes + tardios
