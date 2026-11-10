"""Calculos puros de la linea de tiempo de auditoria (cobros, hito 6): validar los filtros, escribir cada evento en una frase y
mezclar las distintas fuentes en un solo orden. Sin base de datos ni Django: `auditoria.py` lee las tablas y usa esto."""
from datetime import date

from .comprobante_calculos import importe

TIPOS = ('pago', 'movimiento', 'caja', 'factura', 'mesa')
LIMITE_DEFECTO = 100
LIMITE_MAX = 500
DESPLAZAMIENTO_MAX = 5000


class FiltroInvalido(ValueError):
    def __init__(self, campo, mensaje):
        super().__init__(mensaje)
        self.campo = campo


def _entero(params, campo, minimo=1, maximo=None):
    crudo = params.get(campo)
    if crudo in (None, ''):
        return None
    try:
        valor = int(crudo)
    except (TypeError, ValueError):
        raise FiltroInvalido(campo, 'Debe ser un numero entero.')
    if valor < minimo or (maximo is not None and valor > maximo):
        raise FiltroInvalido(campo, f'Debe estar entre {minimo} y {maximo}.' if maximo else f'Debe ser {minimo} o mayor.')
    return valor


def _fecha(params, campo):
    crudo = params.get(campo)
    if crudo in (None, ''):
        return None
    try:
        return date.fromisoformat(str(crudo))
    except ValueError:
        raise FiltroInvalido(campo, 'Debe ser una fecha con formato AAAA-MM-DD (ej: 2026-11-08).')


def validar_filtros(params):
    """De los parametros de la URL a los filtros ya validados. `desde` y `hasta` incluyen el dia entero."""
    desde, hasta = _fecha(params, 'desde'), _fecha(params, 'hasta')
    if desde and hasta and desde > hasta:
        raise FiltroInvalido('desde', 'No puede ser posterior a "hasta".')
    tipos = None
    if params.get('tipo') not in (None, ''):
        tipos = tuple(t.strip().lower() for t in str(params['tipo']).split(',') if t.strip())
        malos = [t for t in tipos if t not in TIPOS]
        if malos or not tipos:
            raise FiltroInvalido('tipo', f"Valores validos (separados por coma): {', '.join(TIPOS)}.")
    limite = _entero(params, 'limite', 1, LIMITE_MAX) or LIMITE_DEFECTO
    desplazamiento = _entero(params, 'desplazamiento', 0, DESPLAZAMIENTO_MAX) or 0
    return {
        'desde': desde, 'hasta': hasta, 'tipos': tipos, 'limite': limite, 'desplazamiento': desplazamiento,
        'empleado': _entero(params, 'empleado'), 'mesa': _entero(params, 'mesa'),
        'caja': _entero(params, 'caja'), 'factura': _entero(params, 'factura'), 'pago': _entero(params, 'pago'),
    }


def incluye(filtros, tipo):
    return filtros['tipos'] is None or tipo in filtros['tipos']


# ---------- una frase por evento ----------

def _evento(fecha_hora, tipo, codigo, descripcion, empleado=None, mesa=None, factura=None, pago=None, caja=None, monto=None, moneda=None):
    return {
        'fecha_hora': fecha_hora, 'tipo': tipo, 'evento': codigo, 'descripcion': descripcion, 'empleado': empleado,
        'mesa': mesa, 'factura': factura, 'pago': pago, 'caja': caja, 'monto': monto, 'moneda': moneda,
    }


def evento_de_pago(fila):
    """`fila`: fecha_hora, evento, estado_anterior, estado_nuevo, detalle, empleado, mesa, factura, pago, medio, monto."""
    texto = f"Pago #{fila['pago']} ({fila['medio']}): {fila['evento']}"
    if fila.get('estado_anterior') and fila['estado_anterior'] != fila['estado_nuevo']:
        texto += f" ({fila['estado_anterior']} -> {fila['estado_nuevo']})"
    elif not fila.get('estado_anterior'):
        texto += f" ({fila['estado_nuevo']})"
    if fila.get('detalle'):
        texto += f". {fila['detalle']}"
    return _evento(fila['fecha_hora'], 'pago', fila['evento'], texto, fila.get('empleado'), fila.get('mesa'), fila.get('factura'),
                   fila['pago'], None, fila.get('monto'), 'ARS')


def evento_de_movimiento(fila):
    """`fila`: fecha_hora, tipo (Ingreso|Egreso), concepto, medio, moneda, monto, descripcion, empleado, caja, pago, mesa, factura."""
    verbo = 'Ingreso' if fila['tipo'] == 'Ingreso' else 'Egreso'
    texto = f"{verbo} de {importe(fila['monto'], fila['moneda'])} en caja #{fila['caja']} ({fila['medio']}): {fila['concepto']}"
    if fila.get('pago'):
        texto += f" del pago #{fila['pago']}"
    if fila.get('descripcion'):
        texto += f". {fila['descripcion']}"
    return _evento(fila['fecha_hora'], 'movimiento', f"{fila['concepto']}", texto, fila.get('empleado'), fila.get('mesa'),
                   fila.get('factura'), fila.get('pago'), fila['caja'], fila['monto'], fila['moneda'])


def evento_de_caja(fila, cierre):
    """Apertura o cierre de una caja. `fila`: caja, fecha_hora, empleado y, al cerrar, esperado y declarado en pesos."""
    if not cierre:
        return _evento(fila['fecha_hora'], 'caja', 'Apertura', f"Se abrio la caja #{fila['caja']}.", fila.get('empleado'), caja=fila['caja'])
    texto = f"Se cerro la caja #{fila['caja']}."
    esperado, declarado = fila.get('esperado'), fila.get('declarado')
    if esperado is not None and declarado is not None:
        diferencia = declarado - esperado
        texto += f" Esperado {importe(esperado)}, declarado {importe(declarado)}"
        texto += ', sin diferencia.' if diferencia == 0 else f", diferencia {importe(diferencia)}."
    return _evento(fila['fecha_hora'], 'caja', 'Cierre', texto, fila.get('empleado'), caja=fila['caja'])


def evento_de_factura(fila, anulacion):
    """`fila`: fecha_hora, empleado, mesa, factura, total y, si se anulo, motivo."""
    if not anulacion:
        texto = f"Se emitio la factura #{fila['factura']} de la mesa {fila['mesa']} por {importe(fila['total'])}."
        return _evento(fila['fecha_hora'], 'factura', 'Emision', texto, fila.get('empleado'), fila['mesa'], fila['factura'], monto=fila['total'], moneda='ARS')
    texto = f"Se anulo la factura #{fila['factura']} de la mesa {fila['mesa']} ({importe(fila['total'])})."
    if fila.get('motivo'):
        texto += f" Motivo: {fila['motivo']}."
    return _evento(fila['fecha_hora'], 'factura', 'Anulacion', texto, fila.get('empleado'), fila['mesa'], fila['factura'], monto=fila['total'], moneda='ARS')


def evento_de_mesa(fila):
    """Cierre de mesa FORZADO (con saldo pendiente). `fila`: fecha_hora, empleado, mesa, motivo."""
    texto = f"Se cerro la mesa {fila['mesa']} con saldo pendiente."
    if fila.get('motivo'):
        texto += f" Motivo: {fila['motivo']}."
    return _evento(fila['fecha_hora'], 'mesa', 'Cierre forzado', texto, fila.get('empleado'), fila['mesa'])


# ---------- mezcla ----------

def mezclar(listas, limite, desplazamiento=0):
    """Junta las fuentes, las ordena de lo mas nuevo a lo mas viejo y devuelve (pagina, hay_mas). Cada fuente tiene que haber
    traido al menos `desplazamiento + limite + 1` eventos (los mas nuevos que cumplen el filtro) para que el orden sea exacto."""
    todos = [evento for lista in listas for evento in lista]
    todos.sort(key=lambda e: (e['fecha_hora'], e['tipo'], str(e['evento']), e['pago'] or 0, e['caja'] or 0), reverse=True)
    pagina = todos[desplazamiento:desplazamiento + limite]
    return pagina, len(todos) > desplazamiento + limite
