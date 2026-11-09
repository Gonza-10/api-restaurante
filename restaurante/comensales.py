"""Comensales, primera ronda y seguridad de la mesa (el acceso a la base y a Redis; las reglas puras estan en comensales_calculos).

- ingresar_comensal: cada dispositivo de una mesa Grupal escribe su nombre; el mismo nombre en la misma mesa es la misma persona.
- marcar_ok / liberar_primera_ronda: las comandas de la primera ronda de una mesa Grupal quedan `retenida` (ya descontaron stock,
  la cocina no las ve) hasta que todos los comensales activos dan el OK o el mozo las libera.
- cancelar_comanda: solo una comanda `retenida` o `pendiente`; devuelve el stock y la saca de la cuenta.
- regenerar_pin: cambia el PIN de la MISMA sesion (lo ya pedido y comido queda en la cuenta) y, de quienes se fueron, cancela lo
  que todavia no se empezo a preparar.
"""
import secrets

from django.db import connection, transaction
from django.utils import timezone

from .comensales_calculos import (
    ACTIVO, ESTADOS_CANCELABLES, GRUPAL, PENDIENTE, RETENIDA, RETIRADO, agregar_pin_anterior, clave_nombre, comandas_a_cancelar,
    faltan_por_ok, limpiar_nombre, mensaje_comensal_retirado, segundos_para_regenerar, texto_motivo_cancelacion, todos_dieron_ok,
)
from .cuenta import ReglaCuenta, factura_vigente
from .estado_comandas import estado_de, transicionar
from .models import ComandaRecibida, Comensal, PedidoCabecera, PedidoDetalle
from .stock import devolver_comanda


class NoSePuedeCancelar(Exception):
    """La comanda ya empezo a prepararse (o ya salio) justo ahora: no se cancela. Deshace lo que se haya hecho en el intento."""


class CuentaEnCurso(NoSePuedeCancelar):
    """La mesa ya tiene la factura emitida: sus renglones estan congelados y no se pueden sacar de la cuenta."""


def _bloquear(sesion_id):
    # sin select_related: en SQL Server el bloqueo con joins puede tomar candados de mas tablas
    return PedidoCabecera.objects.select_for_update().get(pk=sesion_id)


def _id_de_comanda(uuid_comanda):
    """Id de la comanda a partir de su UUID, o None. Se consulta con SQL directo (igual que worker.py y worker_pdf.py): el filtro del
    ORM por un UUID falla con el controlador de SQL Server."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT Id FROM ComandaRecibida WHERE IdComandaUuid = %s', [str(uuid_comanda)])
        fila = cursor.fetchone()
    return fila[0] if fila else None


def _abierta(sesion):
    if sesion.estado != 'Abierto':
        raise ReglaCuenta('La sesion ya esta cerrada.')


# ---------- lectura ----------

def generar_pin_libre():
    """PIN de 4 digitos que no este en uso por ninguna otra sesion abierta (None si no hay)."""
    en_uso = set(PedidoCabecera.objects.filter(estado='Abierto').values_list('codigo_pin', flat=True))
    for _ in range(100):
        pin = f'{secrets.randbelow(10000):04d}'
        if pin not in en_uso:
            return pin
    return None


def resumen_mesa(sesion):
    """Estado de los comensales y de la primera ronda: lo que consultan los dispositivos de la mesa cada pocos segundos."""
    comensales = list(sesion.comensales.order_by('id'))
    return {
        'modalidad': sesion.modalidad,
        'ronda_liberada': sesion.ronda_liberada,
        'espera_ok': sesion.modalidad == GRUPAL and not sesion.ronda_liberada,
        'comensales': [
            {'id': c.id, 'nombre': c.nombre, 'estado': c.estado, 'ok': c.ok_primera_ronda} for c in comensales
        ],
        'faltan_por_ok': faltan_por_ok([(c.nombre, c.estado, c.ok_primera_ronda) for c in comensales])
        if sesion.modalidad == GRUPAL and not sesion.ronda_liberada else [],
    }


# ---------- ingreso y OK ----------

def ingresar_comensal(sesion_id, nombre):
    """Registra al comensal en la mesa (o lo reconoce si ya estaba: mismo nombre, sin distinguir mayusculas ni acentos).
    Un comensal retirado que vuelve con el PIN nuevo se reactiva. Devuelve (comensal, situacion): 'nuevo', 'existente'
    o 'reactivado'."""
    try:
        nombre = limpiar_nombre(nombre)
    except ValueError as error:
        raise ReglaCuenta(str(error), estado=400)
    with transaction.atomic():
        sesion = _bloquear(sesion_id)
        _abierta(sesion)
        clave = clave_nombre(nombre)
        existente = next((c for c in sesion.comensales.all() if clave_nombre(c.nombre) == clave), None)
        if existente is not None:
            if existente.estado == RETIRADO:
                existente.estado = ACTIVO
                existente.fecha_hora_retiro = None
                existente.ok_primera_ronda = False
                existente.save(update_fields=['estado', 'fecha_hora_retiro', 'ok_primera_ronda'])
                return existente, 'reactivado'
            return existente, 'existente'
        comensal = Comensal.objects.create(pedido_cabecera=sesion, nombre=nombre, fecha_hora_ingreso=timezone.now())
        return comensal, 'nuevo'


def comensal_de_sesion(sesion_id, comensal_id):
    """El comensal si pertenece a la sesion, o None."""
    return Comensal.objects.filter(pk=comensal_id, pedido_cabecera_id=sesion_id).first()


def _liberar_bloqueado(sesion):
    """Marca la primera ronda como liberada y pasa a `pendiente` las comandas retenidas. La sesion ya esta bloqueada."""
    sesion.ronda_liberada = True
    sesion.save(update_fields=['ronda_liberada'])
    liberadas = 0
    for comanda in sesion.comandas.filter(estado='Aceptada'):
        cambio, _ = transicionar(comanda.id_comanda_uuid, (RETENIDA,), PENDIENTE)
        liberadas += 1 if cambio else 0
    return liberadas


def marcar_ok(sesion_id, comensal_id, ok=True):
    """El comensal avisa que ya pidio todo lo que queria en la primera ronda ("nada mas por ahora" tambien cuenta), o lo retira.
    Si con eso todos los comensales activos dieron el OK, la primera ronda sale a cocina. Devuelve (sesion, liberada_ahora)."""
    with transaction.atomic():
        sesion = _bloquear(sesion_id)
        _abierta(sesion)
        comensal = comensal_de_sesion(sesion.id, comensal_id)
        if comensal is None:
            raise ReglaCuenta('Ese comensal no está en la mesa.', estado=404)
        if comensal.estado == RETIRADO:
            raise ReglaCuenta(mensaje_comensal_retirado(), estado=403, codigo='comensal_retirado')
        if sesion.modalidad != GRUPAL or sesion.ronda_liberada:
            return sesion, False   # no hay nada que esperar
        comensal.ok_primera_ronda = bool(ok)
        comensal.save(update_fields=['ok_primera_ronda'])
        todos = [(c.estado, c.ok_primera_ronda) for c in sesion.comensales.all()]
        if ok and todos_dieron_ok(todos):
            _liberar_bloqueado(sesion)
            return sesion, True
        return sesion, False


def reiniciar_ok(sesion_id, comensal_id):
    """Pidio algo mas antes de que saliera la primera ronda: su OK vuelve a cero (sigue armando su pedido)."""
    Comensal.objects.filter(pk=comensal_id, pedido_cabecera_id=sesion_id, ok_primera_ronda=True).update(ok_primera_ronda=False)


def liberar_primera_ronda(sesion_id):
    """El mozo libera la primera ronda sin esperar el OK de todos. Devuelve la cantidad de comandas que salieron a cocina
    (0 si ya estaba liberada)."""
    with transaction.atomic():
        sesion = _bloquear(sesion_id)
        _abierta(sesion)
        if sesion.modalidad != GRUPAL:
            raise ReglaCuenta('La mesa es familiar: los pedidos salen a cocina sin esperar a nadie.')
        if sesion.ronda_liberada:
            return 0
        return _liberar_bloqueado(sesion)


# ---------- cancelar comandas ----------

def _cancelar_bloqueado(sesion, comanda, motivo, empleado):
    """Cancela una comanda con la sesion ya bloqueada. Todo o nada: si la cocina la mueve justo ahora, lanza NoSePuedeCancelar y
    se deshace lo hecho (por eso el estado en Redis se cambia al final)."""
    if estado_de(comanda.id_comanda_uuid) not in ESTADOS_CANCELABLES:
        raise NoSePuedeCancelar()
    if factura_vigente(sesion) is not None:
        raise CuentaEnCurso()   # el total de la factura esta congelado: los renglones no se tocan
    items = [(d.cantidad, d.producto.nombre) for d in comanda.detalles.select_related('producto').order_by('id')]
    devolver_comanda(comanda.id, empleado=empleado, id_jornada=sesion.jornada_id, motivo='Comanda cancelada')
    for detalle in list(comanda.detalles.all()):
        detalle.delete()    # los renglones salen de la cuenta (con sus extras, quitados y platos compartidos)
    ComandaRecibida.objects.filter(pk=comanda.id).update(
        estado='Cancelada', motivo=texto_motivo_cancelacion(motivo, items), fecha_hora_cancelacion=timezone.now())
    cambio, _ = transicionar(comanda.id_comanda_uuid, ESTADOS_CANCELABLES, None)
    if not cambio:
        raise NoSePuedeCancelar()
    return items


def cancelar_comanda(uuid_comanda, empleado, motivo=None, id_empleado_sesion=None):
    """Cancela una comanda que todavia no se empezo a preparar (`retenida` o `pendiente`): devuelve el stock y la saca de la
    cuenta. Devuelve la comanda. 404 si no existe, 409 si ya empezo a prepararse o ya no es cancelable."""
    motivo = (motivo or '').strip()[:150] or 'cancelada por el personal'
    id_comanda = _id_de_comanda(uuid_comanda)
    comanda = ComandaRecibida.objects.select_related('pedido_cabecera').filter(pk=id_comanda).first() if id_comanda else None
    if comanda is None:
        raise ReglaCuenta('No existe esa comanda.', estado=404)
    if id_empleado_sesion is not None and comanda.pedido_cabecera.empleado_id != id_empleado_sesion:
        raise ReglaCuenta('No existe esa comanda.', estado=404)   # un mozo solo toca las de sus mesas
    try:
        with transaction.atomic():
            sesion = _bloquear(comanda.pedido_cabecera_id)
            comanda = ComandaRecibida.objects.get(pk=comanda.id)
            if comanda.estado != 'Aceptada':
                raise ReglaCuenta(f'La comanda ya está {comanda.estado.lower()}.')
            _cancelar_bloqueado(sesion, comanda, motivo, empleado)
    except CuentaEnCurso:
        raise ReglaCuenta('La cuenta de la mesa ya está en curso (factura emitida): no se pueden cancelar pedidos. '
                          'Un Admin o Gerente puede anular la factura primero.', codigo='cuenta_en_curso')
    except NoSePuedeCancelar:
        raise ReglaCuenta('La comanda ya empezó a prepararse (o ya se entregó): no se puede cancelar.', codigo='no_cancelable')
    return ComandaRecibida.objects.get(pk=comanda.id)


def resolver_comandas_sin_entregar(sesion, empleado, motivo):
    """Cierre forzado de una mesa con pedidos sin entregar (la sesion ya esta bloqueada): los que no empezaron a prepararse se
    cancelan con devolucion de stock y los demas (en preparacion o listos) se dan por entregados. Devuelve
    (canceladas, entregadas)."""
    canceladas = entregadas = 0
    for comanda in sesion.comandas.filter(estado='Aceptada'):
        if estado_de(comanda.id_comanda_uuid) is None:
            continue
        try:
            with transaction.atomic():   # punto de guardado: si no se puede cancelar, se da por entregada
                _cancelar_bloqueado(sesion, comanda, motivo, empleado)
            canceladas += 1
            continue
        except NoSePuedeCancelar:
            pass
        cambio, _ = transicionar(comanda.id_comanda_uuid, None, None)
        entregadas += 1 if cambio else 0
    return canceladas, entregadas


# ---------- regenerar el PIN ----------

def regenerar_pin(sesion_id, retirados_ids=(), quien='', empleado=None, respetar_espera=False):
    """Cambia el PIN de la sesion (la mesa sigue siendo la misma: lo ya pedido y comido queda en la cuenta). Los dispositivos con
    el PIN viejo quedan afuera. `retirados_ids`: los comensales que se fueron de la mesa; de cada uno se cancela lo que todavia
    no empezo a prepararse (stock devuelto) y lo que esta en proceso o ya salio queda en la cuenta. Sin retirados no se cancela
    nada. Devuelve un diccionario con el PIN nuevo, los retirados y las comandas canceladas."""
    with transaction.atomic():
        sesion = _bloquear(sesion_id)
        _abierta(sesion)
        if respetar_espera:
            falta = segundos_para_regenerar(sesion.pin_regenerado_en, timezone.now())
            if falta > 0:
                raise ReglaCuenta(f'Ya se pidió un PIN nuevo hace instantes. Esperá {falta} segundos para pedir otro.',
                                  estado=429, codigo='espera_pin', segundos=falta)

        retirados = []
        ids = {int(i) for i in (retirados_ids or [])}
        if ids:
            encontrados = {c.id: c for c in sesion.comensales.filter(id__in=ids)}
            desconocidos = sorted(ids - set(encontrados))
            if desconocidos:
                raise ReglaCuenta(f'Hay comensales que no están en la mesa: {desconocidos}.', estado=400)
            retirados = [c for c in encontrados.values() if c.estado == ACTIVO]

        pin_nuevo = None
        for _ in range(100):
            candidato = generar_pin_libre()
            if candidato is None:
                raise ReglaCuenta('No hay PINs disponibles.', estado=503)
            if candidato != sesion.codigo_pin.strip():
                pin_nuevo = candidato
                break
        if pin_nuevo is None:
            raise ReglaCuenta('No se pudo generar un PIN nuevo. Intentá de nuevo.', estado=503)

        ahora = timezone.now()
        canceladas = []
        for comensal in retirados:
            comensal.estado = RETIRADO
            comensal.fecha_hora_retiro = ahora
            comensal.ok_primera_ronda = False
            comensal.save(update_fields=['estado', 'fecha_hora_retiro', 'ok_primera_ronda'])

        if retirados:
            ids_retirados = {c.id for c in retirados}
            nombre = {c.id: c.nombre for c in retirados}
            candidatas = [(c.id, c.comensal_id, estado_de(c.id_comanda_uuid))
                          for c in sesion.comandas.filter(estado='Aceptada', comensal_id__in=ids_retirados)]
            for id_comanda in comandas_a_cancelar(candidatas, ids_retirados):
                comanda = ComandaRecibida.objects.get(pk=id_comanda)
                try:
                    with transaction.atomic():   # punto de guardado: si una no se puede cancelar, las demas siguen
                        items = _cancelar_bloqueado(
                            sesion, comanda, f'{nombre[comanda.comensal_id]} se retiró de la mesa', empleado)
                except NoSePuedeCancelar:
                    continue   # justo empezo a prepararse: queda en la cuenta de la mesa
                canceladas.append({
                    'id_comanda_uuid': str(comanda.id_comanda_uuid), 'comensal': nombre[comanda.comensal_id],
                    'items': [{'cantidad': cantidad, 'nombre': nombre_item} for cantidad, nombre_item in items],
                })

        sesion.pins_anteriores = agregar_pin_anterior(sesion.pins_anteriores, sesion.codigo_pin.strip())
        sesion.codigo_pin = pin_nuevo
        sesion.pin_regenerado_en = ahora
        sesion.pin_regenerado_por = (quien or '')[:80] or None
        sesion.aviso_pin_pendiente = True
        sesion.save(update_fields=['pins_anteriores', 'codigo_pin', 'pin_regenerado_en', 'pin_regenerado_por', 'aviso_pin_pendiente'])

        # los que se fueron ya no cuentan para el OK: si con eso los que quedan estan todos listos, sale la primera ronda
        if sesion.modalidad == GRUPAL and not sesion.ronda_liberada:
            todos = [(c.estado, c.ok_primera_ronda) for c in sesion.comensales.all()]
            if todos_dieron_ok(todos):
                _liberar_bloqueado(sesion)

        return {
            'pin': pin_nuevo,
            'retirados': [{'id': c.id, 'nombre': c.nombre} for c in retirados],
            'comandas_canceladas': canceladas,
            'sesion': sesion,
        }


def marcar_aviso_pin_visto(sesion_id):
    """El mozo confirma que vio el aviso de PIN nuevo (deja de mostrarse como urgente)."""
    return PedidoCabecera.objects.filter(pk=sesion_id, estado='Abierto').update(aviso_pin_pendiente=False)
