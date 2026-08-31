# Sistema de Gestión Gastronómica — API REST

## Introducción

Este repositorio contiene el desarrollo del backend para un sistema de gestión gastronómica, realizado como Actividad de Evaluación N°1 (AE1) de la asignatura Paradigmas y Lenguajes de Programación III, en la carrera de Ingeniería en Sistemas de Información de la Universidad Cuenca del Plata (UCP), Sede Posadas. El proyecto es el primer hito de un desarrollo incremental más amplio, que continuará ampliándose a lo largo del cuatrimestre.

La API expone operaciones CRUD sobre las entidades centrales de un restaurante — menú, mesas, empleados y pedidos — organizadas en una arquitectura en capas sobre Django REST Framework.

## Stack tecnológico

- **Lenguaje:** Python 3.14
- **Framework principal:** Django (arquitectura MVC nativa)
- **Framework API:** Django REST Framework (serialización, validaciones y respuestas HTTP estandarizadas)
- **Persistencia:** SQL Server (vía `mssql-django`)
- **Configuración:** variables de entorno con `python-decouple`

## Cómo crear tu propio entorno

El proyecto todavía se ejecuta de forma local — cada persona que quiera trabajar sobre él necesita armar su propio entorno en su máquina, siguiendo estos pasos:

1. Clonar el repositorio:

git clone https://github.com/Gonza-10/api-restaurante.git

2. Crear y activar un entorno virtual propio:

python -m venv venv
.\venv\Scripts\Activate.ps1

3. Instalar exactamente las mismas dependencias que usa el proyecto, a partir de `requirements.txt`:

pip install -r requirements.txt

4. Crear un archivo `.env` propio en la raíz del proyecto, tomando `.env.example` como plantilla, y completar los datos de conexión a tu instancia local de SQL Server.
5. Tener SQL Server instalado localmente, crear una base de datos vacía, y ejecutar `Script_Creacion_RestauranteDB.sql` sobre ella (por ejemplo, desde SQL Server Management Studio).
6. Crear un superusuario propio para poder acceder al panel de administración

**Cómo crear un superusuario**
- Ejecutar en la terminal:

python manage.py createsuperuser

- El comando va a pedir, en orden: un nombre de usuario, un email (opcional, se puede dejar en blanco) y una contraseña (se pide dos veces, para confirmar).
- La contraseña tiene que tener al menos 8 caracteres, no puede ser completamente numérica ni una contraseña demasiado común (por ejemplo, `12345678` o `password` van a ser rechazadas). Si Django avisa esto y se quiere continuar de todas formas, se puede forzar respondiendo `y` ante la pregunta `Bypass password validation and create user anyway?` — no recomendado para un usuario que se vaya a usar de verdad, solo aceptable para pruebas locales rápidas.


7. Levantar el servidor de desarrollo:

python manage.py runserver


## Endpoints disponibles

| Recurso | Endpoint | Operaciones |
|---|---|---|
| Categorías | `/api/categorias/` | GET, POST, PUT, DELETE |
| Productos | `/api/productos/` | GET, POST, PUT, DELETE (con filtros `?categoria=`, `?vegetariano=true`, `?celiaco=true`) |
| Mesas | `/api/mesas/` | GET, POST, PUT, DELETE |
| Empleados | `/api/empleados/` | GET, POST, PUT, DELETE |
| Pedidos | `/api/pedidos/` | GET, POST, PUT, DELETE |
| Detalle de pedidos | `/api/detalles-pedido/` | GET, POST, PUT, DELETE |

## Estado actual y próximas entregas

El CRUD completo y probado corresponde a la entidad principal del AE1 (`Producto`), junto con las entidades operativas necesarias para sostenerlo (`Categoria`, `Mesa`, `Empleado`, `PedidoCabecera`, `PedidoDetalle`).

Las siguientes entidades ya están modeladas y creadas en la base de datos, pero su lógica y exposición vía API quedan pendientes para las próximas entregas (AE2/TIFAS):

- Autenticación real de empleados (login) y sesión por código PIN para clientes
- `Reserva` — gestión de reservas
- `MetodoPago`, `Pago`, `Factura`, `CotizacionMoneda` — cobro y conversión de moneda
- `Caja`, `MovimientoCaja` — apertura/cierre de caja y movimientos de dinero
- `Rol` — permisos diferenciados por tipo de empleado (Jefe, Administrador, Mozo)
- `ProductoSugerido` — sugerencias de productos adicionales en el menú
- Integración con la API de Mercado Pago para pagos ficticios
- Panel de estadísticas para el rol Jefe

## Integrantes

- Noguera David
- Viarengo Gonzalo
