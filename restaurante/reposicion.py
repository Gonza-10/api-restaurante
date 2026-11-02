"""Lista de reposicion (hito 6): que hay que comprar y que hay que elaborar para volver al stock objetivo.

Los insumos que se compran se agrupan por proveedor principal, con el costo estimado a la ultima compra. Los que se
elaboran (salsa, masa) dicen cuantas tandas hacen falta. Solo la ven Admin y Gerente (lleva costos).
"""
from django.utils import timezone

from .models import Receta, StockInsumo
from .stock import proveedores_por_insumo, ultimo_costo
from .stock_calculos import entra_en_reposicion, plan_reposicion, redondear_dinero, texto_cantidad, CERO


def armar_reposicion(todos=False):
    filas_vista = [
        f for f in StockInsumo.objects.filter(activo=True)
        if entra_en_reposicion(f.estado, f.stock_actual, f.stock_objetivo, todos)
    ]
    ids = [f.insumo_id for f in filas_vista]
    rindes = dict(
        Receta.objects.filter(insumo_producido_id__in=ids).values_list('insumo_producido_id', 'rinde')
    )
    proveedores = proveedores_por_insumo([i for i in ids if i not in rindes])
    filas = []
    for f in filas_vista:
        principal = next((p for p in proveedores.get(f.insumo_id, []) if p['es_principal']), None)
        if principal is None and proveedores.get(f.insumo_id):
            principal = proveedores[f.insumo_id][0]
        filas.append({
            'id': f.insumo_id, 'nombre': f.nombre, 'tipo_medida': f.tipo_medida, 'estado': f.estado,
            'porcentaje': f.porcentaje, 'stock': f.stock_actual, 'objetivo': f.stock_objetivo,
            'costo': ultimo_costo(f.insumo_id) if f.insumo_id not in rindes else None,
            'proveedor': {'id': principal['id'], 'nombre': principal['nombre']} if principal else None,
            'rinde': rindes.get(f.insumo_id),
        })
    plan = plan_reposicion(filas, todos=todos)
    medidas = {f['id']: f['tipo_medida'] for f in filas}

    def decorar(item):
        medida = medidas[item['insumo']]
        item['stock_texto'] = texto_cantidad(item['stock'], medida)
        item['objetivo_texto'] = texto_cantidad(item['objetivo'], medida)
        item['faltante_texto'] = texto_cantidad(item['faltante'], medida)
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
        'total_insumos': sum(len(g['items']) for g in plan['comprar']) + len(plan['producir']),
        'costo_estimado_total': redondear_dinero(total),
        'costo_completo': completo,
        'comprar': plan['comprar'],
        'producir': plan['producir'],
    }
