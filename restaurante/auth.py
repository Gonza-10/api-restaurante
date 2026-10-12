"""
Autenticacion y permisos por rol.

- El login (POST /api/v1/login) devuelve un token firmado con SECRET_KEY y con vencimiento.
- El token solo guarda el id del empleado: el rol y el estado (activo/baja) se leen de la base
  en cada pedido, asi un cambio de rol o una baja tienen efecto inmediato.
- Cada vista declara quien puede leer (roles_lectura) y quien puede escribir (roles_escritura).
  None = publico. Si una vista no declara nada, se exige Admin o Gerente (falla cerrado).
"""
from django.conf import settings
from django.core import signing
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Empleado

SALT_TOKEN = 'savagegrill.auth.v1'

ROL_MOZO = 'Mozo'
ROL_COCINA = 'Cocina'
ROL_ADMIN = 'Admin'
ROL_GERENTE = 'Gerente'

ADMIN_GERENTE = frozenset({ROL_ADMIN, ROL_GERENTE})
SOLO_GERENTE = frozenset({ROL_GERENTE})
SALON = frozenset({ROL_MOZO, ROL_ADMIN, ROL_GERENTE})
COCINA = frozenset({ROL_COCINA, ROL_ADMIN, ROL_GERENTE})


def ttl_token_segundos():
    return getattr(settings, 'TOKEN_TTL_SEGUNDOS', 12 * 60 * 60)


def emitir_token(empleado):
    return signing.dumps({'id': empleado.id}, salt=SALT_TOKEN)


class UsuarioEmpleado:
    """Lo que DRF expone como request.user cuando el token es valido."""
    is_authenticated = True
    is_anonymous = False

    def __init__(self, empleado):
        self.empleado = empleado
        self.id = empleado.id
        self.rol = empleado.rol.nombre

    def __str__(self):
        return f'{self.empleado} ({self.rol})'


class TokenEmpleadoAuthentication(BaseAuthentication):
    """Authorization: Bearer <token>. Sin encabezado = anonimo (las vistas publicas siguen andando)."""

    def authenticate(self, request):
        partes = get_authorization_header(request).split()
        if not partes or partes[0].lower() != b'bearer':
            return None
        if len(partes) != 2:
            raise AuthenticationFailed('Encabezado Authorization invalido.')
        try:
            token = partes[1].decode()
        except UnicodeError:
            raise AuthenticationFailed('Token invalido.')

        try:
            datos = signing.loads(token, salt=SALT_TOKEN, max_age=ttl_token_segundos())
        except signing.SignatureExpired:
            raise AuthenticationFailed('La sesion expiro. Inicie sesion nuevamente.')
        except signing.BadSignature:
            raise AuthenticationFailed('Token invalido.')

        empleado = Empleado.objects.select_related('rol').filter(id=datos.get('id'), activo=True).first()
        if empleado is None:
            raise AuthenticationFailed('El empleado no existe o fue dado de baja.')
        return (UsuarioEmpleado(empleado), token)

    def authenticate_header(self, request):
        return 'Bearer'  # hace que un acceso sin credenciales responda 401 y no 403


class PermisoPorRol(BasePermission):
    message = 'No tiene permisos para realizar esta accion.'

    def has_permission(self, request, view):
        atributo = 'roles_lectura' if request.method in SAFE_METHODS else 'roles_escritura'
        roles = getattr(view, atributo, ADMIN_GERENTE)
        if roles is None:
            return True
        usuario = request.user
        return bool(getattr(usuario, 'is_authenticated', False)) and usuario.rol in roles
