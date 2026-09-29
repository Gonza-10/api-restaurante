# Sistema de Gestión Gastronómica — API REST

## Introducción

Este repositorio contiene el desarrollo del backend para un sistema de gestión gastronómica ("Savage Grill"), realizado en el marco de la asignatura Paradigmas y Lenguajes de Programación III, en la carrera de Ingeniería en Sistemas de Información de la Universidad Cuenca del Plata (UCP), Sede Posadas.

El proyecto se desarrolla de forma incremental a lo largo del cuatrimestre:

- **AE1** (versión grupal 1.0): CRUD base sobre las entidades centrales del restaurante — menú, mesas, empleados y pedidos.
- **AE2** (evolución individual 2.0 — este documento): profundización del flujo de comandas mediante arquitectura distribuida y asíncrona (RabbitMQ, Redis), idempotencia, concurrencia y generación de comprobantes.
- **AE4** (integración final): pendiente — pagos, autenticación real, alta disponibilidad, observabilidad.

La API expone operaciones sobre las entidades centrales de un restaurante, organizadas en una arquitectura en capas sobre Django REST Framework, con un flujo de comandas desacoplado mediante mensajería asíncrona.

## Stack tecnológico

- **Lenguaje:** Python 3.14
- **Framework principal:** Django (arquitectura MVC nativa)
- **Framework API:** Django REST Framework (serialización, validaciones y respuestas HTTP estandarizadas)
- **Persistencia:** SQL Server (vía `mssql-django`)
- **Mensajería asíncrona:** RabbitMQ (vía `pika`)
- **Caché y estado efímero:** Redis (vía `redis-py`)
- **Generación de comprobantes:** `fpdf2`
- **Configuración:** variables de entorno con `python-decouple`
- **Contenedores (infraestructura de RabbitMQ/Redis):** Docker / Docker Compose

## Cómo crear tu propio entorno

El proyecto se ejecuta de forma local — cada persona que quiera trabajar sobre él necesita armar su propio entorno en su máquina, siguiendo estos pasos:

### 1. Clonar el repositorio y ubicarse en la rama correspondiente

```powershell
git clone https://github.com/Gonza-10/api-restaurante.git
cd api-restaurante
git checkout AE2/Noguera_David-Backend
```

### 2. Crear y activar un entorno virtual propio

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Instalar las dependencias

```powershell
pip install -r requirements.txt
```

### 4. Configurar las variables de entorno

Crear un archivo `.env` propio en la raíz del proyecto, tomando `.env.example` como plantilla, con al menos las siguientes variables:

```
DB_NAME=RestauranteDB
DB_HOST=localhost\SQLEXPRESS
SECRET_KEY=<clave-propia>
DEBUG=True
GRUPO=savagegrill
RABBIT_USER=<usuario-propio>
RABBIT_PASS=<contraseña-propia>
```

### 5. Preparar la base de datos SQL Server

1. Tener SQL Server instalado localmente.
2. Crear una base de datos vacía llamada `RestauranteDB`.
3. Ejecutar `Script_Creacion_RestauranteDB.sql` sobre ella (por ejemplo, desde SQL Server Management Studio) para crear el esquema completo.
4. Ejecutar `Script_Seed_AE2.sql` a continuación, para cargar datos de prueba reproducibles (roles, un empleado, las 3 mesas, categorías, productos y una sesión de mesa abierta), sin necesidad de cargarlos manualmente.

### 6. Levantar RabbitMQ y Redis (Docker)

Ambos servicios corren en contenedores. Si usás Docker Desktop de forma nativa en Windows, alcanza con:

```bash
docker compose up -d
```

en la carpeta del proyecto (donde está `docker-compose.yml`).

Si tu entorno de Windows no soporta Docker Desktop nativamente, una alternativa es usar Docker Engine sobre WSL2:

```bash
# Desde una terminal de WSL2 (Ubuntu), en cualquier carpeta accesible por Docker:
docker compose up -d
```

Verificar que ambos contenedores estén corriendo:

```bash
docker ps
```

Deberían aparecer dos contenedores: uno para RabbitMQ (puertos `5672` y `15672`) y otro para Redis (puerto `6379`). El panel de administración de RabbitMQ queda disponible en `http://localhost:15672`, con el usuario y contraseña definidos en `.env`.

### 7. Crear un superusuario propio (para el panel de administración de Django)

```powershell
python manage.py createsuperuser
```

El comando pide, en orden: nombre de usuario, email (opcional) y contraseña (se pide dos veces, para confirmar). La contraseña debe tener al menos 8 caracteres, no puede ser completamente numérica ni una contraseña demasiado común.

### 8. Levantar los procesos del sistema

El backend de AE2 requiere **tres procesos corriendo en simultáneo**, cada uno en su propia terminal:

```powershell
# Terminal 1 — servidor web
python manage.py runserver 8080

# Terminal 2 — worker de comandas (RabbitMQ → SQL Server)
python restaurante/worker.py

# Terminal 3 — worker de comprobantes (genera el PDF al marcar una comanda como "lista")
python restaurante/worker_pdf.py
```

Con los tres procesos corriendo, los tres frontends (`catalogo.html`, `admin.html`, `cocina.html`, abiertos directamente desde el explorador de archivos) pueden operar contra la API en `http://localhost:8080/api/v1/`.

## Endpoints disponibles

| Recurso | Endpoint | Operaciones |
|---|---|---|
| Categorías | `/api/v1/categorias` | GET, POST, PATCH, DELETE |
| Productos | `/api/v1/productos` | GET, POST, PATCH, DELETE (filtros `?categoria=`, `?vegetariano=true`, `?celiaco=true`, `?incluir_inactivos=true`) |
| Mesas | `/api/v1/mesas` | GET, POST, PATCH, DELETE |
| Empleados | `/api/v1/empleados` | GET, POST, PATCH, DELETE |
| Sesiones de mesa | `/api/v1/sesiones-mesa` | GET, POST, PATCH, DELETE (apertura/cierre de mesa por el mozo) |
| Detalle de pedidos | `/api/v1/detalles-pedido` | GET, POST, PATCH, DELETE |
| **Comandas (cliente)** | `POST /api/v1/pedidos` | Crea una comanda, la encola en RabbitMQ (`202 Accepted`) |
| **Tablero de cocina** | `GET /api/v1/pedidos` | Lista las comandas activas con su estado (lee de SQL Server + Redis) |
| **Avance de estado** | `PATCH /api/v1/pedidos/{uuid}/estado` | Cambia el estado de una comanda (`pendiente`/`proceso`/`listo`/`entregado`) |
| **Comprobante PDF** | `GET /api/v1/pedidos/{uuid}/ticket` | Descarga el comprobante generado de forma asíncrona |

> Nota: a diferencia de AE1, las rutas no llevan barra final (`/api/v1/productos`, no `/api/v1/productos/`), para evitar redirecciones que puedan degradar peticiones `POST` a `GET` en algunos navegadores.

## Evolución AE1 → AE2

- **Versión base de AE1:** tag `v1.0-ae1` (commit `c0f7eac`).
- **Punto de partida individual de AE2:** tag `ae2-david-base` (commit `8430cca`, último commit de la rama de Frontend al momento de iniciar el desarrollo individual).
- **Rama individual:** `AE2/Noguera_David-Backend`.
- El desarrollo de AE2 no modifica el esquema de las entidades de AE1, salvo la incorporación de una tabla nueva (`ComandaRecibida`) para el control de idempotencia.

## Arquitectura del flujo de comandas (AE2)

```
Cliente (catalogo.html)
     │  POST /api/v1/pedidos
     ▼
Django (ComandaCreateView) ──valida sesión de mesa──► RabbitMQ (comandas_pendientes)
                                                              │
                                                              ▼
                                                    worker.py (consumidor)
                                                    - valida idempotencia (UNIQUE en SQL)
                                                    - agrupa ítems repetidos
                                                    - persiste en ComandaRecibida + PedidoDetalle
                                                    - escribe estado inicial en Redis
                                                              │
                                                              ▼
Cocina (cocina.html) ◄── polling cada 5s ── GET /api/v1/pedidos (SQL Server + Redis)
     │  PATCH .../estado {"estado": "listo"}
     ▼
Django (ComandaEstadoUpdateView) ──si estado="listo"──► RabbitMQ (comandas_listas)
                                                              │
                                                              ▼
                                                    worker_pdf.py (consumidor)
                                                    - genera el comprobante PDF
                                                    - lo guarda en /tickets
```

## Estado actual y próximas entregas

**Completado en AE2 (individual, backend):**
- Flujo de comandas con RabbitMQ (dos flujos asíncronos independientes: creación de comanda y generación de comprobante).
- Idempotencia garantizada a nivel de base de datos (restricción `UNIQUE` sobre el UUID de la comanda).
- Concurrencia resuelta en la apertura de sesión de mesa (índice único filtrado en SQL Server).
- Caché de catálogo con Redis (TTL + invalidación explícita).
- Estado efímero de cocina gestionado en Redis (sin persistir en SQL Server).
- Generación asíncrona de comprobante PDF.
- Script de datos semilla (`Script_Seed_AE2.sql`), probado en una base limpia.

**Diferido explícitamente a AE4 (fuera del alcance de AE2):**
- Autenticación real de empleados (login) y validación real del PIN de mesa.
- `Reserva` — gestión de reservas.
- `MetodoPago`, `Pago`, `Factura`, `CotizacionMoneda` — cobro y conversión de moneda.
- `Caja`, `MovimientoCaja` — apertura/cierre de caja y movimientos de dinero.
- `Rol` — permisos diferenciados por tipo de empleado (Jefe, Administrador, Mozo) a nivel de API.
- `ProductoSugerido` — sugerencias de productos adicionales en el menú.
- Integración con la API de Mercado Pago (pagos ficticios).
- Panel de estadísticas para el rol Jefe.
- Alta disponibilidad, observabilidad, CI/CD y resiliencia (timeouts, reintentos, Circuit Breaker).

## Gestión de tareas

El desarrollo se organizó mediante un tablero Kanban en GitHub Projects (columnas Ideas, Pendiente, En progreso, Testear, Terminado), con issues individuales referenciados en los commits correspondientes.

## Integrantes

- Noguera David (Backend)
- Viarengo Gonzalo (Frontend)
