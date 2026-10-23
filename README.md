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
SECRET_KEY=<clave-propia>   # larga y aleatoria: con ella se firman los tokens de login
DEBUG=True
GRUPO=savagegrill
RABBIT_USER=<usuario-propio>
RABBIT_PASS=<contraseña-propia>
```

Para generar una `SECRET_KEY` propia:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> Nunca reutilizar la clave de ejemplo ni subir el `.env`: quien conozca la `SECRET_KEY` puede fabricar tokens de cualquier rol.

### 5. Preparar la base de datos SQL Server

1. Tener SQL Server instalado localmente.
2. Crear una base de datos vacía llamada `RestauranteDB`.
3. Ejecutar `sql/Script_Creacion_RestauranteDB.sql` sobre ella (por ejemplo, desde SQL Server Management Studio) para crear el esquema base.
4. Ejecutar, en este orden, los scripts de migración (todos son idempotentes: se pueden correr más de una vez, y en una base nueva completan lo que el script de creación no incluye):
   1. `sql/Script_AE2_Migraciones.sql` — tabla `ComandaRecibida` (idempotencia de comandas).
   2. `sql/Script_AE4_Mesas_Migraciones.sql` — `Mesa.Activa` (baja lógica) y `Mesa.Numero` único.
   3. `sql/Script_AE4_Productos_Migraciones.sql` — `Producto.Descripcion` y `Producto.ImagenUrl`.
   4. `sql/Script_AE4_Sesiones_Migraciones.sql` — una sola sesión abierta por mesa, PIN único entre sesiones abiertas, y sincronización de `Mesa.Estado`.
   5. `sql/Script_AE4_Comandas_Migraciones.sql` — `PedidoDetalle.IdComandaRecibida`: cada ítem queda ligado a la comanda que lo pidió.
   6. `sql/Script_AE4_Cuenta_Migraciones.sql` — `PedidoCabecera.FechaHoraSolicitaCuenta`: cuándo el cliente pidió la cuenta.
   7. `sql/Script_AE4_Tiempos_Migraciones.sql` — `Producto.TiempoEstimadoMin` y `Producto.Porciones` (los valores iniciales los carga el seed).
   8. `sql/Script_AE4_Jornada_Migraciones.sql` — tablas `Turno` (horarios de atención; carga Almuerzo 10:00–15:00 y Cena 20:00–00:30 de ejemplo) y `Jornada`, y `PedidoCabecera.IdJornada`.
   9. `sql/Script_AE4_Especiales_Migraciones.sql` — tablas `Especial` y `DiaEspecial` (calendario de especiales). Requiere haber ejecutado antes el 8.
5. Ejecutar `sql/Script_Seed_AE4.sql` para cargar datos de prueba reproducibles (4 roles, empleados de cada rol, 9 mesas, categorías y 35 productos). Es idempotente: se puede volver a ejecutar sin duplicar filas. No carga sesiones de mesa: las abre el mozo desde la API. Usuarios y contraseñas de prueba: ver la tabla de abajo.

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

### Usuarios de prueba

Cargados por `sql/Script_Seed_AE4.sql`. Todos usan la misma contraseña, **solo para desarrollo** (cambiarla antes de habilitar un login real; este repositorio es público):

| Usuario | Contraseña | Rol | Nombre |
|---|---|---|---|
| `jperez` | `1234` | Mozo | Juan Perez |
| `mvera` | `1234` | Mozo | Marcos Vera |
| `cruiz` | `1234` | Cocina | Carla Ruiz |
| `agomez` | `1234` | Admin | Ana Gomez |
| `lmartinez` | `1234` | Gerente | Luis Martinez |

> Para iniciar sesión: `POST /api/v1/login` con `{"usuario": "agomez", "contrasena": "1234"}`. En Postman, pegar el `token` recibido en Authorization → Bearer Token.

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

Con los tres procesos corriendo, los frontends de la carpeta `frontend/` (`catalogo.html`, `admin.html`, `cocina.html`, abiertos directamente desde el explorador de archivos) pueden operar contra la API en `http://localhost:8080/api/v1/`.

## Endpoints disponibles

| Recurso | Endpoint | Operaciones |
|---|---|---|
| **Login** | `POST /api/v1/login` | Usuario y contraseña → token firmado (dura 12 h) + datos del empleado. Máx. 5 intentos fallidos cada 5 min por usuario |
| **Mi perfil** | `GET /api/v1/me` | Quién es el dueño del token (cualquier rol) |
| Categorías | `/api/v1/categorias` | GET, POST, PATCH, DELETE |
| Productos | `/api/v1/productos` | GET, POST, PATCH, DELETE (filtros combinables, ver abajo) |
| Imagen de producto | `POST /api/v1/productos/{id}/imagen` · `DELETE /api/v1/productos/{id}/imagen` | POST: sube una foto propia (`multipart/form-data`, campo `imagen`; JPG/PNG/WEBP, máx. 2 MB). DELETE: quita la imagen. Para usar una imagen de internet: `PATCH /productos/{id}` con `"imagen_url": "https://..."` |
| Mesas | `/api/v1/mesas` | GET, POST, PATCH, DELETE (baja lógica: `Activa=0`; filtro `?incluir_inactivas=true`; el `Numero` es único) |
| Roles | `GET /api/v1/roles` | Lista `[{id, nombre}]` (Mozo, Cocina, Admin, Gerente), para el formulario de empleados. Solo Gerente |
| Empleados | `/api/v1/empleados` | GET, POST, PATCH, DELETE |
| **Abrir mesa** | `POST /api/v1/sesiones-mesa/abrir` | El mozo sienta clientes: `{"numero_mesa": 2, "cantidad_comensales": 3}`. Valida que la mesa exista, esté libre y que los comensales no superen su capacidad. Genera el PIN, toma al mozo del token y ocupa la mesa. `201` con el `codigo_pin` |
| **Cerrar mesa** | `POST /api/v1/sesiones-mesa/{id}/cerrar` | Cierra la sesión (fecha puesta por el servidor) y libera la mesa. El PIN deja de servir |
| Sesiones de mesa | `GET /api/v1/sesiones-mesa` | Lista (un Mozo ve solo las suyas). Filtros: `?estado=Abierto`, `?mesa=2`. No se crean ni modifican por CRUD genérico |
| **Acceso por PIN** | `POST /api/v1/acceso-mesa` | El cliente ingresa el PIN: `{"pin": "4821"}` → `{"numero_mesa": 2, "cantidad_comensales": 3, "mozo_nombre": "Juan Perez", "fecha_hora_inicio": "2026-10-21T12:00:00-03:00", "solicita_cuenta": false}`. `403` si el PIN es incorrecto o la sesión está cerrada |
| **Solicitar cuenta** | `POST /api/v1/solicitar-cuenta` | El cliente pide la cuenta: `{"numero_mesa": 2, "pin": "4821"}`. Guarda la hora (`fecha_hora_solicita_cuenta`) en la sesión; pedirla de nuevo conserva la primera hora. El mozo la ve como `solicita_cuenta` en `sesiones-mesa` y `mesas` |
| **Historial de la mesa (cliente)** | `POST /api/v1/mesa/historial` | `{"numero_mesa": 2, "pin": "4821"}` → comandas de la sesión con sus ítems (`cantidad`, `sub_total`), `estado` y `total`. Todos los dispositivos de la mesa ven lo mismo. El estado es el de Redis; si ya no está, es `entregado` |
| **Comandas de una sesión (mozo)** | `GET /api/v1/sesiones-mesa/{id}/comandas` | Lo mismo que el historial de la mesa, para el mozo (un Mozo solo ve sus sesiones) |
| **Estado del local** | `GET /api/v1/jornada/actual` | Si hay jornada abierta, de qué turno, desde cuándo, `sugerir_cierre` (pasó el horario del turno) y el turno que corresponde a esta hora. Público; los nombres del personal solo se ven con sesión iniciada |
| **Comenzar jornada** | `POST /api/v1/jornada/abrir` | Admin o Gerente. `{"turno": 2}` (opcional: si falta, usa el turno que corresponde a la hora). `409` si ya hay una abierta. Sin jornada abierta no se abren mesas ni se aceptan comandas |
| **Cerrar jornada** | `POST /api/v1/jornada/cerrar` | Admin o Gerente. No cierra las mesas que siguen sentadas: ya no piden, pero se pueden cobrar. Devuelve `advertencias` con las mesas que quedaron abiertas. Nunca se cierra sola |
| Jornadas | `GET /api/v1/jornadas` | Historial (Admin, Gerente). Filtros: `?estado=Abierta`, `?fecha=2026-10-23`, `?turno=2` |
| **Turnos** | `/api/v1/turnos` | Horarios de atención (`{"nombre": "Cena", "hora_apertura": "20:00", "hora_cierre": "00:30"}`; si el cierre es menor que la apertura, termina al día siguiente). GET público; POST, PATCH y DELETE (baja lógica) solo Gerente |
| **Especiales** | `/api/v1/especiales` | Plato con precio especial: regla semanal (`{"producto": 5, "precio_especial": 6000, "dia_semana": 2}`, 1=lunes … 7=domingo) o fecha puntual (`"fecha": "2026-10-31"`, con `"reemplaza_semanales": true/false`). `"turno"` opcional (sin turno vale todo el día). El precio especial debe ser menor al normal. Filtros: `?dia_semana=`, `?fecha=`, `?producto=` |
| Calendario de especiales | `GET /api/v1/especiales/calendario?mes=2026-10` | El mes día por día, con los especiales ya resueltos (cada uno indica su `origen`: `semanal` o `fecha`) |
| Especiales vigentes | `GET /api/v1/especiales/vigentes` | Los que valen ahora: los de la fecha y el turno de la jornada abierta. Sin jornada, ninguno |
| Fechas puntuales | `GET /api/v1/especiales/fechas` · `PUT` / `DELETE /api/v1/especiales/fechas/2026-10-31` | PUT: `{"reemplaza_semanales": true, "nota": "Día del Padre"}`. Con `true` y sin especiales cargados ese día, no hay especiales. DELETE borra la fecha y sus especiales |
| Detalle de pedidos | `/api/v1/detalles-pedido` | GET, POST, PATCH, DELETE |
| **Comandas (cliente)** | `POST /api/v1/pedidos` | Crea una comanda, la encola en RabbitMQ (`202 Accepted`). Exige el `pin` de la mesa en el cuerpo: `{"id_comanda_uuid": "...", "mesa_id": 2, "pin": "4821", "items": [{"id": 1}]}`. `409` si la mesa no tiene sesión abierta, `403` si el PIN no coincide |
| **Tablero de cocina** | `GET /api/v1/pedidos` | Lista las comandas activas con su estado (lee de SQL Server + Redis) |
| **Avance de estado** | `PATCH /api/v1/pedidos/{uuid}/estado` | Cambia el estado de una comanda (`pendiente`/`proceso`/`listo`/`entregado`) |
| **Comprobante PDF** | `GET /api/v1/pedidos/{uuid}/ticket` | Descarga el comprobante generado de forma asíncrona |

## Autenticación y permisos

Los endpoints protegidos exigen el encabezado `Authorization: Bearer <token>`. Sin token responden `401`; con token de un rol sin permiso, `403`. El rol y el estado del empleado se consultan en la base en cada pedido: una baja o un cambio de rol rige de inmediato.

| Recurso | Lectura (GET) | Escritura (POST / PATCH / DELETE) |
|---|---|---|
| Menú (`productos`, `categorias`) | Público | Admin, Gerente |
| Imagen de producto | Público | Admin, Gerente |
| Mesas | Mozo, Admin, Gerente | Admin, Gerente |
| Roles y empleados | Gerente | Gerente (el DELETE es baja lógica; no puede darse de baja ni cambiarse el rol a sí mismo, y debe quedar al menos un Gerente activo) |
| Abrir / cerrar mesa, detalle de pedido | Mozo, Admin, Gerente | Mozo, Admin, Gerente (un Mozo solo ve y cierra sus propias sesiones) |
| Turnos (horarios de atención) | Público | Gerente |
| Estado de la jornada (`GET /jornada/actual`), especiales (calendario, vigentes) | Público | — |
| Abrir / cerrar jornada, historial de jornadas | Admin, Gerente | Admin, Gerente |
| Especiales (crear, editar, borrar, fechas puntuales) | Público | Admin, Gerente |
| Tablero de cocina (`GET /pedidos`, `/cocina/tablero`) | Cocina, Admin, Gerente | — |
| Cambio de estado de comanda | — | Cocina, Admin, Gerente |
| Enviar comanda (`POST /pedidos`), acceso por PIN, solicitar cuenta e historial de la mesa | — | Público, protegido por el PIN de la mesa (máx. 10 PIN erróneos cada 5 min por IP) |
| Comprobante PDF | Público | — |

**Filtros de `GET /api/v1/productos`** (todos opcionales y combinables entre sí; el listado completo, sin filtros, se cachea en Redis):

| Parámetro | Ejemplo | Efecto |
|---|---|---|
| `categoria` | `?categoria=2` · `?categoria=1,3` | Una o varias categorías (ids, separados por coma) |
| `vegetariano` | `?vegetariano=true` | Solo vegetarianos |
| `sin_tacc` (o `celiaco`) | `?sin_tacc=true` | Solo aptos celíacos |
| `buscar` | `?buscar=burger` | Texto en nombre o descripción |
| `precio_min` / `precio_max` | `?precio_max=8000` | Rango de precio |
| `orden` | `?orden=precio` · `-precio` · `nombre` · `-nombre` | Orden del resultado |
| `incluir_inactivos` | `?incluir_inactivos=true` | Incluye productos dados de baja (vista de admin) |

Cada producto trae también `categoria_nombre`, para agrupar el menú sin una segunda consulta a `/categorias`, y `tiempo_estimado` (minutos de preparación) y `porciones` (personas que come), ambos opcionales y editables con PATCH. Un valor inválido devuelve `400` con el parámetro que falló.

Si el plato es especial en la jornada abierta, trae además `precio_especial` y `es_especial_hoy: true` (si no, `null` y `false`); `precio` sigue siendo el normal, para que el front muestre ambos. El listado cacheado se invalida al abrir o cerrar la jornada y al editar los especiales.

> Imágenes de producto: `imagen_url` es un link `https://` externo o una ruta local `/media/productos/<archivo>`, que se sirve desde el mismo servidor (`http://localhost:8080/media/productos/<archivo>`; el front debe anteponer el host de la API). Las fotos subidas se guardan en la carpeta `media/` (no se versiona). El nombre lo genera el servidor y el formato se valida por contenido, no por extensión.

> Nota: a diferencia de AE1, las rutas no llevan barra final (`/api/v1/productos`, no `/api/v1/productos/`), para evitar redirecciones que puedan degradar peticiones `POST` a `GET` en algunos navegadores.

## Jornadas y especiales

- **Jornada:** periodo en que el local está abierto al público. Hay una sola abierta a la vez y puede haber varias por día (un turno cada una: almuerzo, cena…). La abren y cierran Admin o Gerente con un botón; los horarios de los turnos solo *sugieren* el turno al abrir y *avisan* (`sugerir_cierre`) cuando conviene cerrar, pero nunca abren ni cierran nada solos.
- **Sin jornada abierta** no se abren mesas ni se aceptan comandas. Cobrar las mesas que quedaron, el stock y lo administrativo siguen disponibles. Una mesa pertenece a la jornada en la que se abrió, aunque se cobre después de cerrarla o pasada la medianoche; las mesas de una jornada cerrada no aceptan pedidos nuevos. Las sesiones anteriores a las jornadas (sin jornada) piden mientras haya alguna abierta.
- **Especiales:** reglas semanales (todos los martes, etc.) más excepciones por fecha. Una fecha puede *reemplazar* a los especiales semanales de ese día o *sumarse* a ellos (`reemplaza_semanales`). Si un plato está en las dos capas, gana la fecha. Cada especial puede limitarse a un turno. **El día y el turno que valen los define la jornada abierta**, no el reloj: una jornada abierta el viernes a las 20 sigue usando los especiales del viernes pasada la medianoche.
- **Precio en la comanda:** el worker cobra el precio especial vigente de la jornada de la mesa y lo guarda en `PedidoDetalle.PrecioUnitario`, así que cambiar el calendario después no toca las comandas ya tomadas. Nunca se cobra más que el precio normal.

## Estructura del repositorio

```
├── config/            configuración de Django (settings, urls)
├── restaurante/       API: modelos, vistas, serializers, auth, workers (RabbitMQ)
├── sql/               scripts de base de datos (creación, migraciones, seed)
├── frontend/          páginas HTML, app.js, styles.css y fonts (Gonzalo)
├── legacy/            servidor de ejemplo de AE1 (SERV_WEB.py), fuera del sistema actual
├── tickets/           PDFs generados (no se versiona)
├── media/             fotos de productos subidas (no se versiona)
├── docker-compose.yml RabbitMQ + Redis
├── manage.py · requirements.txt · .env.example
└── README.md · CLAUDE.md
```

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
- Script de datos semilla (`sql/Script_Seed_AE4.sql`, reemplaza al de AE2), idempotente.

**Diferido explícitamente a AE4 (fuera del alcance de AE2):**
- `Reserva` — gestión de reservas.
- `MetodoPago`, `Pago`, `Factura`, `CotizacionMoneda` — cobro y conversión de moneda.
- `Caja`, `MovimientoCaja` — apertura/cierre de caja y movimientos de dinero.
- `ProductoSugerido` — sugerencias de productos adicionales en el menú.
- Integración con la API de Mercado Pago (pagos ficticios).
- Panel de estadísticas para el rol Jefe.
- Alta disponibilidad, observabilidad, CI/CD y resiliencia (timeouts, reintentos, Circuit Breaker).

## Gestión de tareas

El desarrollo se organizó mediante un tablero Kanban en GitHub Projects (columnas Ideas, Pendiente, En progreso, Testear, Terminado), con issues individuales referenciados en los commits correspondientes.

## Integrantes

- Noguera David (Backend)
- Viarengo Gonzalo (Frontend)
