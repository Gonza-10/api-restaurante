"""Auditoria de cobros (hito 6): linea de tiempo de solo lectura. Admin y Gerente."""
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auditoria import linea_de_tiempo
from .auditoria_calculos import FiltroInvalido, validar_filtros
from .auth import ADMIN_GERENTE
from .serializers_cobros import en_texto


class AuditoriaView(APIView):
    """GET /auditoria. Admin y Gerente. De lo mas nuevo a lo mas viejo. Filtros (todos opcionales, por la URL):
      desde, hasta   AAAA-MM-DD, ambos dias incluidos (hora local)
      tipo           pago, movimiento, caja, factura, mesa (uno o varios separados por coma)
      empleado       id del empleado que hizo la accion
      mesa           numero de mesa          caja, factura, pago   ids
      limite         eventos por pagina (defecto 100, maximo 500)        desplazamiento   cuantos saltear
    Un filtro que no corresponde a un tipo lo deja afuera (ej.: `caja` deja solo movimientos y aperturas/cierres de esa caja).
    Devuelve {"eventos": [{fecha_hora, tipo, evento, descripcion, empleado:{id,nombre}|null, mesa, factura, pago, caja, monto,
    moneda}], "hay_mas": bool, "limite", "desplazamiento"}."""
    roles_lectura = ADMIN_GERENTE

    def get(self, request):
        try:
            filtros = validar_filtros(request.query_params)
        except FiltroInvalido as error:
            raise ValidationError({error.campo: str(error)})
        resultado = linea_de_tiempo(filtros)
        return Response(en_texto({
            'eventos': resultado['eventos'], 'hay_mas': resultado['hay_mas'],
            'limite': filtros['limite'], 'desplazamiento': filtros['desplazamiento'],
        }))
