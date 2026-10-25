"""Vistas de turnos, jornadas y especiales."""
from datetime import date

from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, SOLO_GERENTE
from .catalogo import invalidar_cache_catalogo
from .especiales import calendario_mes, especiales_de_fecha
from .jornadas import advertencia_apertura, advertencia_cierre, jornada_abierta, turno_sugerido
from .models import Turno, Jornada, Especial, DiaEspecial, PedidoCabecera
from .serializers_operacion import (
    TurnoSerializer, JornadaSerializer, JornadaAbrirSerializer, EspecialSerializer, DIAS_SEMANA,
)
from .views import _es_verdadero


def _parsear_fecha(valor, nombre_param):
    try:
        return date.fromisoformat(valor)
    except (ValueError, TypeError):
        raise ValidationError({nombre_param: 'Debe ser una fecha con formato AAAA-MM-DD (ej: 2026-10-23).'})


# ==================== TURNOS ====================

class TurnoViewSet(viewsets.ModelViewSet):
    """Horarios de atencion del local. Los ve cualquiera (el cliente puede mostrar 'abierto de X a Y');
    los edita solo el Gerente."""
    serializer_class = TurnoSerializer
    roles_lectura = None
    roles_escritura = SOLO_GERENTE

    def get_queryset(self):
        queryset = Turno.objects.order_by('hora_apertura', 'id')
        if self.action == 'list' and not _es_verdadero(self.request.query_params.get('incluir_inactivos')):
            queryset = queryset.filter(activo=True)
        return queryset

    def destroy(self, request, *args, **kwargs):
        # baja logica: el turno figura en jornadas y especiales historicos
        turno = self.get_object()
        turno.activo = False
        turno.save(update_fields=['activo'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== JORNADAS ====================

class JornadaViewSet(viewsets.ReadOnlyModelViewSet):
    """Historial de jornadas, para reportes. Filtros: ?estado=Abierta|Cerrada, ?fecha=AAAA-MM-DD, ?turno=id."""
    serializer_class = JornadaSerializer
    roles_lectura = ADMIN_GERENTE

    def get_queryset(self):
        queryset = Jornada.objects.select_related('turno', 'empleado_apertura', 'empleado_cierre').order_by('-id')
        if self.action == 'list':
            p = self.request.query_params
            estado = (p.get('estado') or '').strip().lower()
            if estado:
                if estado not in ('abierta', 'cerrada'):
                    raise ValidationError({'estado': "Valores validos: 'Abierta' o 'Cerrada'."})
                queryset = queryset.filter(estado__iexact=estado)
            if p.get('fecha'):
                queryset = queryset.filter(fecha=_parsear_fecha(p['fecha'], 'fecha'))
            if p.get('turno'):
                queryset = queryset.filter(turno_id=p['turno'])
        return queryset


class JornadaActualView(APIView):
    """Estado del local ahora: si hay jornada abierta, de que turno, hace cuanto, y el turno que
    corresponde a esta hora. Es publico (el cliente puede mostrar 'local cerrado'); los nombres del
    personal solo los ve quien inicio sesion."""
    roles_lectura = None

    def get(self, request):
        jornada = jornada_abierta()
        sugerido = turno_sugerido()
        datos = None
        if jornada is not None:
            datos = JornadaSerializer(jornada).data
            if not getattr(request.user, 'is_authenticated', False):
                for campo in ('apertura_por', 'cierre_por', 'mesas_abiertas'):
                    datos.pop(campo, None)
        return Response({
            'abierta': jornada is not None,
            'jornada': datos,
            'turno_sugerido': TurnoSerializer(sugerido).data if sugerido else None,
        })


class JornadaAbrirView(APIView):
    """'Comenzar jornada'. Solo Admin y Gerente. El turno se elige o se toma el que corresponde a la hora."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request):
        entrada = JornadaAbrirSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        existente = jornada_abierta()
        if existente is not None:
            return Response(
                {'error': f'Ya hay una jornada abierta ({existente.turno.nombre} del {existente.fecha.isoformat()}). '
                          'Cerrarla antes de comenzar otra.',
                 'jornada_abierta': existente.id},
                status=status.HTTP_409_CONFLICT
            )

        turno = entrada.validated_data.get('turno') or turno_sugerido()
        if turno is None:
            turnos = Turno.objects.filter(activo=True).order_by('hora_apertura', 'id')
            return Response(
                {'error': 'Ahora no corresponde a ningun turno. Indicar el turno a abrir.',
                 'turnos': TurnoSerializer(turnos, many=True).data},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                jornada = Jornada.objects.create(
                    turno=turno,
                    fecha=timezone.localdate(),
                    fecha_hora_apertura=timezone.now(),
                    empleado_apertura=request.user.empleado,
                    estado='Abierta',
                )
        except IntegrityError:
            # otra apertura simultanea gano: el indice unico de la base lo garantiza
            return Response({'error': 'Ya hay una jornada abierta.'}, status=status.HTTP_409_CONFLICT)

        invalidar_cache_catalogo()  # los especiales vigentes dependen de la jornada
        aviso = advertencia_apertura(turno)
        datos = dict(JornadaSerializer(jornada).data)
        datos['advertencias'] = [aviso] if aviso else []
        return Response(datos, status=status.HTTP_201_CREATED)


class JornadaCerrarView(APIView):
    """'Cerrar jornada'. Solo Admin y Gerente. No cierra las mesas que siguen sentadas: ya no aceptan
    pedidos nuevos, pero se pueden cobrar. Avisa cuantas quedan abiertas."""
    roles_escritura = ADMIN_GERENTE

    def post(self, request):
        jornada = jornada_abierta()
        if jornada is None:
            return Response({'error': 'No hay una jornada abierta.'}, status=status.HTTP_409_CONFLICT)

        cerradas = Jornada.objects.filter(pk=jornada.pk, estado='Abierta').update(
            estado='Cerrada',
            fecha_hora_cierre=timezone.now(),
            empleado_cierre=request.user.empleado,
        )
        if cerradas == 0:
            return Response({'error': 'La jornada ya estaba cerrada.'}, status=status.HTTP_409_CONFLICT)

        invalidar_cache_catalogo()

        jornada = Jornada.objects.select_related('turno', 'empleado_apertura', 'empleado_cierre').get(pk=jornada.pk)
        abiertas = list(
            PedidoCabecera.objects.filter(jornada=jornada, estado='Abierto')
            .select_related('mesa').order_by('mesa__numero')
        )
        advertencias = []
        aviso = advertencia_cierre(jornada)
        if aviso:
            advertencias.append(aviso)
        if abiertas:
            numeros = ', '.join(str(s.mesa.numero) for s in abiertas)
            advertencias.append(
                f'Quedan {len(abiertas)} mesas abiertas (mesa {numeros}): ya no aceptan pedidos nuevos, '
                'pero se pueden cobrar.'
            )
        return Response({
            'jornada': JornadaSerializer(jornada).data,
            'mesas_abiertas': [s.mesa.numero for s in abiertas],
            'advertencias': advertencias,
        })


# ==================== ESPECIALES ====================

def _item_especial(especial, origen):
    return {
        'id': especial.id,
        'producto': especial.producto_id,
        'producto_nombre': especial.producto.nombre,
        'precio_normal': f'{especial.producto.precio_actual:.2f}',
        'precio_especial': f'{especial.precio_especial:.2f}',
        'turno': especial.turno_id,
        'turno_nombre': especial.turno.nombre if especial.turno else 'Todo el dia',
        'origen': origen,
    }


class EspecialViewSet(viewsets.ModelViewSet):
    """Calendario de especiales. Los ve cualquiera (es parte del menu); los edita Admin y Gerente.
    Filtros del listado: ?dia_semana=1..7, ?fecha=AAAA-MM-DD, ?producto=id."""
    serializer_class = EspecialSerializer
    roles_lectura = None
    roles_escritura = ADMIN_GERENTE

    def get_queryset(self):
        queryset = Especial.objects.select_related('producto', 'turno').order_by('dia_semana', 'fecha', 'id')
        if self.action == 'list':
            p = self.request.query_params
            if p.get('dia_semana'):
                try:
                    dia = int(p['dia_semana'])
                except ValueError:
                    dia = 0
                if not 1 <= dia <= 7:
                    raise ValidationError({'dia_semana': 'Debe ser un numero de 1 (lunes) a 7 (domingo).'})
                queryset = queryset.filter(dia_semana=dia)
            if p.get('fecha'):
                queryset = queryset.filter(fecha=_parsear_fecha(p['fecha'], 'fecha'))
            if p.get('producto'):
                queryset = queryset.filter(producto_id=p['producto'])
        return queryset

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidar_cache_catalogo()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidar_cache_catalogo()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidar_cache_catalogo()

    @action(detail=False, methods=['get'], url_path='calendario')
    def calendario(self, request):
        """Un mes completo, dia por dia, con los especiales ya resueltos (semanales + fechas puntuales).
        ?mes=AAAA-MM (por defecto, el mes actual)."""
        texto = (request.query_params.get('mes') or '').strip()
        if texto:
            try:
                anio, mes = (int(x) for x in texto.split('-'))
                date(anio, mes, 1)
            except ValueError:
                raise ValidationError({'mes': 'Debe tener formato AAAA-MM (ej: 2026-10).'})
        else:
            hoy = timezone.localdate()
            anio, mes = hoy.year, hoy.month

        dias = []
        for dia in calendario_mes(anio, mes):
            config = dia['config']
            dias.append({
                'fecha': dia['fecha'].isoformat(),
                'dia_semana': dia['fecha'].isoweekday(),
                'dia_nombre': DIAS_SEMANA[dia['fecha'].isoweekday()],
                'fecha_configurada': config is not None,
                'reemplaza_semanales': config.reemplaza if config else False,
                'nota': config.nota if config else None,
                'especiales': [_item_especial(e, origen) for e, origen in dia['especiales']],
            })
        return Response({'mes': f'{anio:04d}-{mes:02d}', 'dias': dias})

    @action(detail=False, methods=['get'], url_path='vigentes')
    def vigentes(self, request):
        """Los especiales que valen ahora: los de la jornada abierta (su fecha y su turno). Sin jornada, ninguno."""
        jornada = jornada_abierta()
        if jornada is None:
            return Response({'jornada': None, 'especiales': []})
        items = [
            _item_especial(e, origen)
            for e, origen in especiales_de_fecha(jornada.fecha)
            if e.turno_id is None or e.turno_id == jornada.turno_id
        ]
        return Response({
            'jornada': jornada.id,
            'fecha': jornada.fecha.isoformat(),
            'turno': jornada.turno.nombre,
            'especiales': items,
        })

    @action(detail=False, methods=['get'], url_path='fechas')
    def fechas(self, request):
        """Fechas puntuales configuradas. ?desde=AAAA-MM-DD&hasta=AAAA-MM-DD (opcionales)."""
        queryset = DiaEspecial.objects.order_by('fecha')
        p = request.query_params
        if p.get('desde'):
            queryset = queryset.filter(fecha__gte=_parsear_fecha(p['desde'], 'desde'))
        if p.get('hasta'):
            queryset = queryset.filter(fecha__lte=_parsear_fecha(p['hasta'], 'hasta'))
        return Response([
            {
                'fecha': c.fecha.isoformat(),
                'reemplaza_semanales': c.reemplaza,
                'nota': c.nota,
                'cantidad_especiales': Especial.objects.filter(fecha=c.fecha).count(),
            }
            for c in queryset
        ])

    @action(detail=False, methods=['put', 'delete'], url_path=r'fechas/(?P<fecha>[0-9]{4}-[0-9]{2}-[0-9]{2})',
            url_name='fecha')
    def fecha(self, request, fecha=None):
        """PUT: configura una fecha puntual: {"reemplaza_semanales": true, "nota": "Dia del Padre"}.
        Con reemplaza_semanales=true y sin especiales cargados para esa fecha, ese dia no hay especiales.
        DELETE: borra la configuracion de la fecha y los especiales que tenia."""
        dia = _parsear_fecha(fecha, 'fecha')

        if request.method == 'DELETE':
            with transaction.atomic():
                Especial.objects.filter(fecha=dia).delete()
                DiaEspecial.objects.filter(fecha=dia).delete()
            invalidar_cache_catalogo()
            return Response(status=status.HTTP_204_NO_CONTENT)

        reemplaza = request.data.get('reemplaza_semanales', False)
        if not isinstance(reemplaza, bool):
            raise ValidationError({'reemplaza_semanales': 'Debe ser true o false.'})
        nota = request.data.get('nota')
        if nota is not None:
            nota = str(nota).strip() or None
            if nota is not None and len(nota) > 100:
                raise ValidationError({'nota': 'Maximo 100 caracteres.'})

        config, _ = DiaEspecial.objects.update_or_create(fecha=dia, defaults={'reemplaza': reemplaza, 'nota': nota})
        invalidar_cache_catalogo()
        return Response({
            'fecha': config.fecha.isoformat(),
            'reemplaza_semanales': config.reemplaza,
            'nota': config.nota,
            'cantidad_especiales': Especial.objects.filter(fecha=dia).count(),
        })
