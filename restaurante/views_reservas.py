"""Reservas de mesa. Las gestionan Admin y Gerente; el mozo solo las consulta."""
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, SALON
from .models import Reserva, Turno
from .reservas import (
    ReglaReserva, actualizar_reserva, ahora_local, cancelar_reserva, crear_reserva, disponibilidad, vencer_reservas,
)
from .serializers_reservas import (
    DisponibilidadFiltroSerializer, ReservaEntradaSerializer, ReservaFiltroSerializer, reserva_a_dict,
)


def _consulta():
    return Reserva.objects.select_related('turno', 'mesa', 'empleado', 'empleado_cancelacion')


def _reserva_o_404(pk):
    reserva = _consulta().filter(pk=pk).first()
    if reserva is None:
        raise Http404
    return reserva


def _error(regla):
    return Response({'error': regla.mensaje, **regla.extra}, status=regla.estado)


class ReservasView(APIView):
    """GET  /reservas  Lista (Mozo, Admin, Gerente). Filtros por la URL, todos opcionales:
         fecha=AAAA-MM-DD | desde=... y hasta=... (sin ninguna fecha: desde hoy)   turno=id   mesa=numero   estado=Confirmada|Cancelada|Cumplida|No se presentó
       POST /reservas  Alta (Admin, Gerente): nombre, apellido, telefono, fecha, turno (id), hora (HH:MM, dentro del turno),
         cantidad_personas y, opcionales, numero_mesa (si falta, el sistema elige la mesa libre mas chica que alcance), notas y
         origen (Llamada, Mensaje u Otro). Responde 201 con la reserva; 409 si la mesa ya está reservada o no hay ninguna libre."""
    roles_lectura = SALON
    roles_escritura = ADMIN_GERENTE

    def get(self, request):
        filtros = ReservaFiltroSerializer(data=request.query_params)
        filtros.is_valid(raise_exception=True)
        f = filtros.validated_data
        vencer_reservas()
        consulta = _consulta()
        if 'fecha' in f:
            consulta = consulta.filter(fecha=f['fecha'])
        else:
            consulta = consulta.filter(fecha__gte=f.get('desde') or ahora_local().date())
            if 'hasta' in f:
                consulta = consulta.filter(fecha__lte=f['hasta'])
        if 'turno' in f:
            consulta = consulta.filter(turno_id=f['turno'])
        if 'mesa' in f:
            consulta = consulta.filter(mesa__numero=f['mesa'])
        if 'estado' in f:
            consulta = consulta.filter(estado=f['estado'])
        consulta = consulta.order_by('fecha', 'turno__hora_apertura', 'hora', 'id')
        return Response([reserva_a_dict(r) for r in consulta])

    def post(self, request):
        entrada = ReservaEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            reserva = crear_reserva(entrada.validated_data, request.user.empleado)
        except ReglaReserva as regla:
            return _error(regla)
        return Response(reserva_a_dict(_reserva_o_404(reserva.id)), status=status.HTTP_201_CREATED)


class ReservaDetalleView(APIView):
    """GET /reservas/{id}  Detalle.
       PATCH /reservas/{id}  Edita una reserva Confirmada (Admin, Gerente): se manda solo lo que cambia. Si cambia fecha, turno,
         hora, personas o mesa se vuelven a validar las reglas. numero_mesa: null = que el sistema elija otra mesa.
       No se borra: una reserva que ya no va se cancela (POST /reservas/{id}/cancelar) y queda en el historial."""
    roles_lectura = SALON
    roles_escritura = ADMIN_GERENTE

    def get(self, request, pk):
        vencer_reservas()
        return Response(reserva_a_dict(_reserva_o_404(pk)))

    def patch(self, request, pk):
        entrada = ReservaEntradaSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        reserva = _reserva_o_404(pk)
        try:
            actualizar_reserva(reserva, entrada.validated_data)
        except ReglaReserva as regla:
            return _error(regla)
        return Response(reserva_a_dict(_reserva_o_404(pk)))


class ReservaCancelarView(APIView):
    """POST /reservas/{id}/cancelar  (Admin, Gerente). Cuerpo opcional: {"motivo": "..."}.
    Solo se cancela una reserva Confirmada. Libera la mesa de inmediato. Queda quién la canceló, cuándo y por qué."""
    roles_lectura = ADMIN_GERENTE
    roles_escritura = ADMIN_GERENTE

    def post(self, request, pk):
        datos = request.data if isinstance(request.data, dict) else {}
        reserva = _reserva_o_404(pk)
        try:
            cancelar_reserva(reserva, request.user.empleado, datos.get('motivo'))
        except ReglaReserva as regla:
            return _error(regla)
        return Response(reserva_a_dict(_reserva_o_404(pk)))


class ReservasDisponibilidadView(APIView):
    """GET /reservas/disponibilidad?fecha=AAAA-MM-DD&turno=id&personas=N  (Mozo, Admin, Gerente).
    Las mesas libres para esa jornada y esa cantidad de personas, de la mas chica a la mas grande, y cual se sugiere."""
    roles_lectura = SALON

    def get(self, request):
        filtros = DisponibilidadFiltroSerializer(data=request.query_params)
        filtros.is_valid(raise_exception=True)
        f = filtros.validated_data
        turno = Turno.objects.filter(id=f['turno']).first()
        if turno is None:
            raise ValidationError({'turno': 'No existe ese turno.'})
        mesas, sugerida = disponibilidad(f['fecha'], turno, f['personas'])
        return Response({
            'fecha': f['fecha'].isoformat(),
            'turno': {'id': turno.id, 'nombre': turno.nombre},
            'personas': f['personas'],
            'mesa_sugerida': sugerida,
            'mesas': [{'numero': m.numero, 'capacidad': m.capacidad_maxima} for m in mesas],
        })
