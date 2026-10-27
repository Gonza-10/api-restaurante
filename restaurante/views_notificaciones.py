"""Vista de las notificaciones del panel de Cocina (hito 3)."""
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import COCINA
from .notificaciones import armar_notificaciones


class NotificacionesCocinaView(APIView):
    """GET /cocina/notificaciones. Cocina, Admin y Gerente. Se calculan en el momento (no se guardan ni se marcan como
    leidas): el panel las consulta cada ~10 segundos y el aviso desaparece cuando se resuelve la situacion.
    Tipos: `plato_sin_insumos` (un plato en carta que no se puede preparar, con los insumos que faltan),
    `insumo_critico` (insumo agotado o en nivel critico) y `se_puede_reactivar` (plato que Cocina agoto a mano y ya
    tiene insumos). Cada una trae `severidad` (urgente / aviso / info), `mensaje` listo para mostrar y los datos del
    plato o del insumo. `resumen` cuenta por tipo y por severidad (para el numerito de la pestana)."""
    roles_lectura = COCINA

    def get(self, request):
        return Response(armar_notificaciones())
