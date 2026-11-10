"""Lista de reposicion (hito 6, mejorada en el 6.1): que hay que comprar y que hay que elaborar.

Dos reglas la hacen confiable:
- Solo cuenta el STOCK UTIL: lo que ya vencio o va a vencer dentro de la ventana de aviso de su insumo no se cuenta,
  porque no se va a poder usar. Si hay 10 kg de harina y 6 kg vencen en 3 dias, para la reposicion hay 4 kg.
- Elaborar necesita ingredientes: para cada elaboracion que hay que producir se verifica que alcancen; lo que falte se
  suma a lo que hay que comprar (o a las tandas de otra elaboracion, si el ingrediente es una elaboracion).
Los insumos que se compran se agrupan por proveedor principal, con el costo estimado a la ultima compra. Solo la ven
Admin y Gerente (lleva costos). El calculo en si esta en stock_calculos.plan_reposicion (puro, se prueba solo).
"""
from django.utils import timezone

from .models import Insumo, Receta, StockInsumo
from .stock import proveedores_por_insumo, ultimo_costo
from .stock_calculos import CERO, plan_reposicion, redondear_dinero, texto_cantidad
from .vencimientos import cantidades_por_vencer, dias_aviso


def armar_reposicion(todos=False, hoy=None):
    hoy = hoy or timezone.localdate()
    insumos = list(Insumo.objects.all())
    stocks = {f.insumo_id: f.stock_actual for f in StockInsumo.objects.all()}
    perdidas = cantidades_por_vencer(hoy)

    recetas = {}
    for receta in Receta.objects.filter(insumo_producido__isnull=False).prefetch_related('ingredientes'):
        recetas[receta.insumo_producido_id] = {
            'rinde': receta.rinde,
            'ingredientes': [(i.insumo_id, i.cantidad) for i in receta.ingredientes.all()],
        }
    proveedores = proveedores_por_insumo([i.id for i in insumos if i.id not in recetas])

    filas = []
    for i in insumos:
        principal = next((p for p in proveedores.get(i.id, []) if p['es_principal']), None)
        if principal is None and proveedores.get(i.id):
            principal = proveedores[i.id][0]
        propio = perdidas.get(i.id, {})
        filas.append({
            'id': i.id, 'nombre': i.nombre, 'tipo_medida': i.tipo_medida, 'activo': i.activo,
            'stock': stocks.get(i.id, CERO), 'a_perder': propio.get('a_perder', CERO), 'vencido': propio.get('vencido', CERO),
            'objetivo': i.stock_objetivo, 'umbral_bajo': i.umbral_bajo_pct, 'umbral_critico': i.umbral_critico_pct,
            'proveedor': {'id': principal['id'], 'nombre': principal['nombre']} if principal else None,
        })
    plan = plan_reposicion(filas, recetas, todos=todos, costo_de=ultimo_costo)

    def decorar(item):
        medida = item['tipo_medida']
        for clave in ('stock', 'a_perder', 'stock_util', 'objetivo', 'faltante'):
            item[f'{clave}_texto'] = texto_cantidad(item[clave], medida)
        for falta in item.get('ingredientes_faltantes', []):
            for clave in ('necesario', 'disponible', 'faltante'):
                falta[f'{clave}_texto'] = texto_cantidad(falta[clave], falta['tipo_medida'])
        if 'rinde' in item:
            item['cantidad_a_producir_texto'] = texto_cantidad(item['cantidad_a_producir'], medida)
        for quien in item.get('para_elaborar', []):
            quien['cantidad_texto'] = texto_cantidad(quien['cantidad'], medida)
        return item

    total = CERO
    completo = True
    for grupo in plan['comprar']:
        grupo['items'] = [decorar(i) for i in grupo['items']]
        total += grupo['total_estimado']
        completo = completo and grupo['completo']
    plan['producir'] = [decorar(i) for i in plan['producir']]
    return {
        'generado': timezone.localtime().isoformat(),
        'criterio': 'todos_bajo_objetivo' if todos else 'solo_los_que_requieren_atencion',
        'dias_aviso': dias_aviso(),
        'total_insumos': sum(len(g['items']) for g in plan['comprar']) + len(plan['producir']),
        'costo_estimado_total': redondear_dinero(total),
        'costo_completo': completo,
        'comprar': plan['comprar'],
        'producir': plan['producir'],
    }
