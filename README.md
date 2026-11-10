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

Variables opcionales para cobrar con Mercado Pago (ver «Cobros (hito 4)»). Sin ninguna, el sistema funciona en **modo simulado** y no necesita internet ni credenciales:

```
MP_MODO=simulado             # simulado (por defecto) | prueba (credenciales de prueba de Mercado Pago) | produccion
MP_ACCESS_TOKEN=<token>      # solo en modo prueba o produccion; lo carga cada integrante en su .env, nunca se sube al repositorio
MP_FRONT_URL=http://localhost:8080   # a donde Mercado Pago devuelve al cliente despues de pagar
MP_EXPIRACION_MIN=30         # minutos de vida del link de pago (minimo 5)
MP_SYNC_INTERVALO_SEG=15     # cada cuanto el worker de Mercado Pago confirma los pagos pendientes
```

### 5. Preparar la base de datos SQL Server

1. Tener SQL Server instalado localmente.
2. Crear una base de datos vacía llamada `RestauranteDB`.
3. Los scripts de `sql/` llevan un número al principio del nombre (`NN_nombre.sql`): se ejecutan **en orden numérico** sobre `RestauranteDB` (por ejemplo, desde SQL Server Management Studio), desde el `00` hasta el `99`. Un script nuevo toma el número siguiente; el seed es siempre el último (`99`). Todos, salvo el `00`, son idempotentes: se pueden correr más de una vez, y en una base nueva completan lo que el script de creación no incluye.

   | N.º | Script | Qué hace |
   |---|---|---|
   | 00 | `00_Creacion_RestauranteDB.sql` | Esquema base (solo en una base vacía; no es idempotente) |
   | 01 | `01_AE2_Migraciones.sql` | Tabla `ComandaRecibida` (idempotencia de comandas) |
   | 02 | `02_AE4_Mesas_Migraciones.sql` | `Mesa.Activa` (baja lógica) y `Mesa.Numero` único |
   | 03 | `03_AE4_Productos_Migraciones.sql` | `Producto.Descripcion` y `Producto.ImagenUrl` |
   | 04 | `04_AE4_Sesiones_Migraciones.sql` | Una sola sesión abierta por mesa, PIN único entre sesiones abiertas y sincronización de `Mesa.Estado` |
   | 05 | `05_AE4_Comandas_Migraciones.sql` | `PedidoDetalle.IdComandaRecibida`: cada ítem queda ligado a la comanda que lo pidió |
   | 06 | `06_AE4_Cuenta_Migraciones.sql` | `PedidoCabecera.FechaHoraSolicitaCuenta`: cuándo el cliente pidió la cuenta |
   | 07 | `07_AE4_Tiempos_Migraciones.sql` | `Producto.TiempoEstimadoMin` y `Producto.Porciones` (los valores iniciales los carga el seed) |
   | 08 | `08_AE4_Jornada_Migraciones.sql` | Tablas `Turno` (carga Almuerzo 10:00–15:00 y Cena 20:00–00:30 de ejemplo) y `Jornada`, y `PedidoCabecera.IdJornada` |
   | 09 | `09_AE4_Especiales_Migraciones.sql` | Tablas `Especial` y `DiaEspecial` (calendario de especiales). Requiere el 08 |
   | 10 | `10_AE4_Disponibilidad_Migraciones.sql` | `Producto.Disponible` (lo calcula el stock), `Producto.AgotadoManual` (override de Cocina) y quién/cuándo lo agotó |
   | 11 | `11_AE4_Stock_Insumos_Migraciones.sql` | Stock, hito 1: `Proveedor`, `Insumo`, `InsumoProveedor`, `Compra`, `LoteInsumo`, `MovimientoStock` y la vista `vw_StockInsumo`. Requiere el 08 |
   | 12 | `12_AE4_Recetas_Migraciones.sql` | Stock, hito 2: `Receta`, `RecetaIngrediente`, `Producto.IdReceta` y `ComandaRecibida.Estado/Motivo/MensajeCliente` (comandas rechazadas por falta de stock). Requiere el 11 |
   | 13 | `13_AE4_Perdidas_Migraciones.sql` | Stock, hito 4: tabla `Perdida` (insumos o platos perdidos, con motivo de lista cerrada) y `MovimientoStock.IdPerdida`. Requiere el 12 |
   | 14 | `14_AE4_Modificadores_Migraciones.sql` | Stock, hito 5: `RecetaIngrediente.EsQuitable` y la tabla `PedidoDetalleModificador` (qué ingredientes se quitaron de cada renglón de un pedido). Requiere el 13 |
   | 15 | `15_AE4_Elaboraciones_Vencimientos_Migraciones.sql` | Stock, hito 6: elaboraciones (`Receta.IdInsumoProducido/Rinde/DiasVencimiento`), tabla `Produccion`, `MovimientoStock.IdProduccion` y la tabla `Configuracion` (días de aviso de vencimiento, 5 por defecto). Requiere el 14 |
   | 16 | `16_AE4_Aviso_Vencimiento_Por_Insumo_Migraciones.sql` | Stock, hito 6.1: `Insumo.DiasAvisoVencimiento` (días de aviso propios de cada insumo; `NULL` = usa los generales). Requiere el 15 |
   | 17 | `17_AE4_Cotizacion_Migraciones.sql` | Cobros, hito 1: `CotizacionMoneda` con `Valor` de 8 decimales, `Fuente` y `FechaHora` (cotización oficial del BCRA de USD, BRL y PYG; la carga sola el worker, nadie la escribe a mano). Requiere el 00 y el 15 |
   | 18 | `18_AE4_Caja_Migraciones.sql` | Cobros, hito 2: `CajaMoneda` (arqueo por moneda), `MovimientoCaja` con medio (`Efectivo` o `MercadoPago`), moneda, cotización, equivalente en pesos y concepto (`Manual`, `Venta`, `Propina`, `Vuelto`, `Anulacion`); `CajaMoneda` también por medio; totales en pesos en `Caja`, y el índice `UQ_Caja_Abierta` (una sola caja abierta). Requiere el 00 y el 17 |
   | 19 | `19_AE4_Cuenta_Pagos_Migraciones.sql` | Cobros, hito 3: métodos de pago (`Efectivo`, `MercadoPago`), `Factura` con estado, total congelado y equivalentes en USD/BRL/PYG (`UQ_Factura_Vigente`: una vigente por sesión), `FacturaDetalle`, `Pago` (estado, moneda, cotización congelada, propina, vuelto, clave de idempotencia; un solo pendiente por factura), `PagoEvento` (historial), `PedidoDetalleCompartido` (plato dividido) y el cierre forzado de mesa en `PedidoCabecera`. Requiere el 00, el 17 y el 18 |
   | 20 | `20_AE4_MercadoPago_Migraciones.sql` | Cobros, hito 4: en `Pago`, los datos de Mercado Pago (`MpPreferenciaId`, `MpUrlPago`, `FechaHoraExpiracion`, `MpPagoId` único, `MpEstado`, `MpMontoNeto`) y el índice `IX_Pago_Estado`; `MovimientoCaja.IdEmpleado` pasa a admitir `NULL` (un cobro aprobado por Mercado Pago lo anota el sistema). Requiere el 19 |
   | 21 | `21_AE4_Extras_Migraciones.sql` | Cobros, hito 5: `RecetaExtra` (los extras que ofrece cada receta: insumo, cuánto gasta y cuánto cuesta una unidad, máximo por plato, `Activo` y `Disponible`; `UQ_RecetaExtra`: un insumo se ofrece una sola vez por receta) y `PedidoDetalleExtra` (los extras de cada renglón del pedido, con el recargo congelado; `UQ_PedidoDetalleExtra`). Requiere el 12 y el 14 |
   | 22 | `22_AE4_Comprobante_Auditoria_Migraciones.sql` | Cobros, hito 6: `Factura.NombreFactura` (a nombre de quién se emite el comprobante PDF; la casilla «quiero factura» ya existía como `SolicitoTicket`) y dos índices por fecha, `IX_PagoEvento_FechaHora` e `IX_MovimientoCaja_FechaHora`, para la línea de tiempo de auditoría. No crea tablas. Requiere el 18 y el 19 |
   | 23 | `23_AE4_Reservas_Migraciones.sql` | Reservas: en `Reserva` suma el turno (`IdTurno`), la cantidad de personas, notas, origen (Llamada, Mensaje u Otro), quién y cuándo la canceló, cuándo se resolvió y qué sesión de mesa la cumplió; estados `Confirmada`, `Cancelada`, `Cumplida` y `No se presentó`; y un índice único que impide dos reservas confirmadas para la misma mesa, fecha y turno. Requiere el 00 y el 08 |
   | 24 | `24_AE4_PagoTarjeta_Migraciones.sql` | Pago con tarjeta: agrega el método `Tarjeta` a `MetodoPago` y `PedidoCabecera.MetodoPagoSolicitado` (con qué medio dijo el cliente que quiere pagar al pedir la cuenta: Efectivo, MercadoPago o Tarjeta). Requiere el 19 |
   | 25 | `25_AE4_Comensales_Seguridad_Migraciones.sql` | Comensales y seguridad de la mesa: `PedidoCabecera` suma la modalidad (Familiar o Grupal), si la primera ronda ya salió a cocina y el aviso de PIN nuevo (quién lo pidió, los PIN anteriores y si el mozo ya lo vio); tabla `Comensal` (nombre único por sesión, activo o retirado, OK de la primera ronda); `ComandaRecibida` suma el comensal y el estado `Cancelada`. Requiere el 00, el 05 y el 12 |
   | 26 | `26_AE4_Barra_Destinos_Migraciones.sql` | Barra y destinos: `Producto.Destino` (COCINA, BARRA o MOZO; NULL = el de su categoría), `PedidoDetalle.Destino` (el del ítem al pedirse; los anteriores quedan en COCINA) y el rol `Bartender`. |
   | 99 | `99_Seed_AE4.sql` | Datos de prueba reproducibles: 4 roles, empleados de cada rol, 9 mesas, categorías y 35 productos. No carga sesiones de mesa: las abre el mozo desde la API. Usuarios y contraseñas de prueba: ver la tabla de abajo |

4. Verificar el entorno: ejecutar `Tests/Scripts/diagnostico_entorno.sql` en SSMS (solo lectura). Cada fila dice `OK` o `FALTA` e indica qué script correr. Cuidado: Django no crea tablas (los modelos son `managed=False`), así que `python manage.py migrate` no reemplaza a los scripts SQL.

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

Cargados por `sql/99_Seed_AE4.sql`. Todos usan la misma contraseña, **solo para desarrollo** (cambiarla antes de habilitar un login real; este repositorio es público):

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

El backend requiere **cinco procesos corriendo en simultáneo** (el cuarto, el de cotización, solo hace falta para cobrar en moneda extranjera, y el quinto, para confirmar los cobros con Mercado Pago), cada uno en su propia terminal:

```powershell
# Terminal 1 — servidor web
python manage.py runserver 8080

# Terminal 2 — worker de comandas (RabbitMQ → SQL Server)
python restaurante/worker.py

# Terminal 3 — worker de comprobantes (genera el PDF al marcar una comanda como "lista")
python restaurante/worker_pdf.py

# Terminal 4 — worker de cotización (consulta al BCRA cada 30 minutos; ver «Cobros (hito 1)»)
python restaurante/worker_cotizacion.py

# Terminal 5 — worker de Mercado Pago (confirma los cobros pendientes cada 15 segundos; ver «Cobros (hito 4)»)
python restaurante/worker_mercadopago.py
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
| **Cerrar mesa** | `POST /api/v1/sesiones-mesa/{id}/cerrar` | Cierra la sesión (fecha puesta por el servidor) y libera la mesa. El PIN deja de servir. Se cierra sin consumo o con la cuenta pagada; con consumo sin cobrar responde `409` (con `total` y `saldo`). Un Admin o Gerente puede forzar el cierre con `{"forzar": true, "motivo": "..."}` (queda registrado y la factura sin pagos se anula); un Mozo no (`403`). Con un pago pendiente no se cierra nunca. Ver «Cobros (hito 3)» |
| Sesiones de mesa | `GET /api/v1/sesiones-mesa` | Lista (un Mozo ve solo las suyas). Filtros: `?estado=Abierto`, `?mesa=2`. No se crean ni modifican por CRUD genérico |
| **Acceso por PIN** | `POST /api/v1/acceso-mesa` | El cliente ingresa el PIN: `{"pin": "4821"}` → `{"numero_mesa": 2, "cantidad_comensales": 3, "mozo_nombre": "Juan Perez", "fecha_hora_inicio": "2026-10-21T12:00:00-03:00", "solicita_cuenta": false}`. `403` si el PIN es incorrecto o la sesión está cerrada |
| **Solicitar cuenta** | `POST /api/v1/solicitar-cuenta` | El cliente pide la cuenta: `{"numero_mesa": 2, "pin": "4821"}`. Guarda la hora (`fecha_hora_solicita_cuenta`) en la sesión; pedirla de nuevo conserva la primera hora. El mozo la ve como `solicita_cuenta` en `sesiones-mesa` y `mesas` |
| **Comensales de la mesa (cliente)** | `POST /api/v1/mesa/comensales` · `/mesa/comensales/estado` · `/mesa/comensales/ok` · `POST /mesa/regenerar-pin` | Ver «Comensales y seguridad de la mesa» |
| **Comensales (personal)** | `GET /sesiones-mesa/{id}/comensales` · `POST /sesiones-mesa/{id}/liberar-ronda` · `POST /sesiones-mesa/{id}/regenerar-pin` · `POST /sesiones-mesa/{id}/pin/visto` · `POST /pedidos/{uuid}/cancelar` | Ver «Comensales y seguridad de la mesa» |
| **Barra y bebidas** | `GET /barra/tablero` · `PATCH /barra/pedidos/{uuid}/estado` · `GET /mozo/bebidas` · `POST /pedidos/{uuid}/bebidas/entregar` | Ver «Barra, bartender y bebidas del mozo». |
| **Historial de la mesa (cliente)** | `POST /api/v1/mesa/historial` | `{"numero_mesa": 2, "pin": "4821"}` → comandas de la sesión con sus ítems (`cantidad`, `sub_total`), `estado` y `total`. Todos los dispositivos de la mesa ven lo mismo. El estado es el de Redis; si ya no está, es `entregado`. Una comanda que el worker rechazó por falta de insumos viene con `estado: "rechazada"`, sin ítems y con `mensaje` para mostrarle al cliente |
| **Comandas de una sesión (mozo)** | `GET /api/v1/sesiones-mesa/{id}/comandas` | Lo mismo que el historial de la mesa, para el mozo (un Mozo solo ve sus sesiones) |
| **Estado del local** | `GET /api/v1/jornada/actual` | Si hay jornada abierta, de qué turno, desde cuándo, `sugerir_cierre` (pasó el horario del turno) y el turno que corresponde a esta hora. Público; los nombres del personal solo se ven con sesión iniciada |
| **Comenzar jornada** | `POST /api/v1/jornada/abrir` | Admin o Gerente. `{"turno": 2}` (opcional: si falta, usa el turno que corresponde a la hora). Con el turno explícito se puede abrir a cualquier hora: si cae fuera de su horario abre igual y devuelve `advertencias`. `409` si ya hay una abierta. Sin jornada abierta no se abren mesas ni se aceptan comandas |
| **Cerrar jornada** | `POST /api/v1/jornada/cerrar` | Admin o Gerente. No cierra las mesas que siguen sentadas: ya no piden, pero se pueden cobrar. Devuelve `advertencias` con las mesas que quedaron abiertas y si se cerró antes del horario previsto del turno. Nunca se cierra sola |
| Jornadas | `GET /api/v1/jornadas` | Historial (Admin, Gerente). Filtros: `?estado=Abierta`, `?fecha=2026-10-23`, `?turno=2` |
| **Turnos** | `/api/v1/turnos` | Horarios de atención (`{"nombre": "Cena", "hora_apertura": "20:00", "hora_cierre": "00:30"}`; si el cierre es menor que la apertura, termina al día siguiente). GET público; POST, PATCH y DELETE (baja lógica) solo Gerente |
| **Especiales** | `/api/v1/especiales` | Plato con precio especial: regla semanal (`{"producto": 5, "precio_especial": 6000, "dia_semana": 2}`, 1=lunes … 7=domingo) o fecha puntual (`"fecha": "2026-10-31"`, con `"reemplaza_semanales": true/false`). `"turno"` opcional (sin turno vale todo el día). El precio especial debe ser menor al normal. Filtros: `?dia_semana=`, `?fecha=`, `?producto=` |
| Calendario de especiales | `GET /api/v1/especiales/calendario?mes=2026-10` | El mes día por día, con los especiales ya resueltos (cada uno indica su `origen`: `semanal` o `fecha`) |
| Especiales vigentes | `GET /api/v1/especiales/vigentes` | Los que valen ahora: los de la fecha y el turno de la jornada abierta. Sin jornada, ninguno |
| Fechas puntuales | `GET /api/v1/especiales/fechas` · `PUT` / `DELETE /api/v1/especiales/fechas/2026-10-31` | PUT: `{"reemplaza_semanales": true, "nota": "Día del Padre"}`. Con `true` y sin especiales cargados ese día, no hay especiales. DELETE borra la fecha y sus especiales |
| **Agotar un plato** | `POST /api/v1/productos/{id}/agotar` | Cocina, Admin o Gerente: marca el plato como «sin insumos». Desaparece del menú del cliente al instante. Es idempotente. Devuelve el producto con `agotado_manual`, `agotado_desde`, `agotado_por` y `visible` |
| **Reactivar un plato** | `POST /api/v1/productos/{id}/reactivar` | Cocina, Admin o Gerente. `409` si el stock todavía no alcanza para prepararlo. El stock nunca reactiva solo un plato agotado a mano |
| **Aviso en tiempo real del menú** | `GET /api/v1/catalogo/eventos` | Público. Flujo SSE (`text/event-stream`): evento `catalogo` con `{"version": N}` al conectar y cada vez que cambia el menú. Ver «Disponibilidad y aviso en tiempo real» |
| Versión del menú | `GET /api/v1/catalogo/version` | Público. `{"version": N}`. Respaldo del flujo en tiempo real: si el número cambió, volver a pedir `/productos` |
| **Proveedores** | `/api/v1/proveedores` | Admin, Gerente. ABM; `DELETE` es baja lógica. `?incluir_inactivos=true`, `?buscar=texto` |
| **Insumos** | `/api/v1/insumos` | Admin, Gerente. ABM de la materia prima: `{"nombre": "Harina", "tipo_medida": "Masa", "stock_objetivo": 150000}` (todo en unidad base: g, ml o unidades). Cada insumo trae `stock_actual`, `porcentaje`, `estado` y `semaforo`. `dias_aviso_vencimiento` (opcional, 0 a 365; `null` = usa los generales) son los días con que se avisa que un lote de ese insumo está por vencer, y `dias_aviso_efectivo` los que realmente se usan. `DELETE` es baja lógica y `409` si todavía tiene stock |
| Proveedores de un insumo | `PUT /api/v1/insumos/{id}/proveedores` | `{"proveedores": [{"proveedor": 1, "es_principal": true}, {"proveedor": 2}]}`: reemplaza la lista; un solo principal |
| **Compras** | `POST /api/v1/compras` · `GET /api/v1/compras` | Admin, Gerente. Una compra a un proveedor con una línea por insumo; cada línea crea un lote. La cantidad va de UNA forma: `"cantidad": 150000` o `"cantidad_presentaciones": 10` + `"tamano_presentacion": 15000`; más `costo_total` y `fecha_vencimiento` (opcional). No se editan ni se borran |
| Lotes | `GET /api/v1/lotes` · `POST /api/v1/lotes/{id}/baja` | Admin, Gerente. Filtros `?insumo=`, `?estado=activo\|agotado\|vencido\|baja`, `?vence_en_dias=N`. La baja saca del stock lo que quedaba (`{"motivo": "texto", "motivo_codigo": "rotura_derrame"}`; el código es opcional: sin él es `vencimiento` si el lote ya venció y `otro` en los demás casos) y queda registrada como pérdida de insumo |
| Libro de movimientos | `GET /api/v1/movimientos-stock` | Admin, Gerente. Todo cambio de stock, más nuevos primero. Filtros `?insumo=`, `?lote=`, `?tipo=`, `?desde=`, `?hasta=`, `?limite=` |
| **Estado del stock** | `GET /api/v1/stock` | Cocina, Admin, Gerente. Insumo por insumo con su `porcentaje` y `semaforo`, lo más grave primero. `?vista=detallada` agrega cuánto hay de cada uno, el objetivo, lotes y próximo vencimiento (Admin y Gerente además costos, valor del stock y proveedor principal). Filtros `?estado=critico,bajo` y `?buscar=` |
| Ajuste por inventario | `POST /api/v1/stock/ajustes` | Admin, Gerente. `{"insumo": 1, "cantidad_real": 50000, "motivo": "..."}`: deja el stock en lo que se contó (descuenta por FEFO, o crea un lote de origen `Ajuste`) |
| Verificación del libro | `GET /api/v1/stock/verificacion` | Admin, Gerente. Comprueba que la suma de los movimientos de cada lote sea igual a su cantidad actual |
| **Recetas** | `/api/v1/recetas` | Qué insumos gasta UNA unidad vendida (`{"nombre": "Tallarines", "ingredientes": [{"insumo": 1, "cantidad": 250}, {"insumo": 2, "cantidad": 2}]}`, cantidades en unidad base; cada ingrediente admite `"quitable": true` para que el cliente pueda pedirlo «sin»). Lectura: Cocina, Admin, Gerente; escritura: Admin, Gerente (el `PUT` reemplaza la lista de ingredientes). Cada receta trae `porciones_posibles` e `insumo_limitante`; Admin y Gerente además `costo`, `costo_completo` y el margen de cada producto. `DELETE` solo si ningún producto la usa (`409`) |
| Receta de un producto | `GET` · `PUT /api/v1/productos/{id}/receta` | `{"receta": 3}` asigna la receta; `{"receta": null}` deja el producto sin control de stock (por ejemplo, una bebida cerrada). Varios productos pueden compartir la misma receta. No está en `PUT /productos/{id}` porque el menú es público |
| **Extras de una receta** | `GET` · `POST /api/v1/recetas/{id}/extras` | Lo que el cliente puede **sumar** a los platos de esa receta, con recargo («más cheddar»). `POST` (Admin, Gerente): `{"insumo": 7, "cantidad": 25, "precio": 500, "max_por_unidad": 2}` (`cantidad` = lo que gasta UNA unidad de extra, en unidad base; `precio` = recargo por unidad; `max_por_unidad` de 1 a 10, por defecto 1; `activo` por defecto `true`). Un insumo se ofrece una sola vez por receta (`400`). `GET`: Cocina, Admin, Gerente. Ver «Cobros (hito 5)» |
| **Un extra** | `GET` · `PUT` · `PATCH` · `DELETE /api/v1/extras/{id}` | `PUT`/`PATCH`: Admin, Gerente (cambian cantidad, precio, máximo o `activo`; el insumo no se cambia: se desactiva y se crea otro). `DELETE`: solo si nunca se usó en un pedido; si no, `409` y se desactiva con `"activo": false` |
| **Copiar extras** | `POST /api/v1/recetas/{id}/extras/copiar` | Admin, Gerente: `{"origen": 3}` copia a esta receta los extras de otra, **sin pisar** los que ya tiene (`201` si copió algo, `200` si no). Devuelve `copiados`, `omitidos_por_existir` y la lista de extras resultante |
| Productos sin receta | `GET /api/v1/productos-sin-receta` | Admin, Gerente. Productos en carta que no descuentan stock: para no olvidarse ninguno |
| Comandas rechazadas | `GET /api/v1/comandas-rechazadas` | Admin, Gerente. Comandas que no se pudieron preparar por falta de stock, con el `motivo` interno (plato, cuántos alcanzaban e insumo que limitó). Filtros `?desde=`, `?hasta=`, `?limite=` |
| **Notificaciones de Cocina** | `GET /api/v1/cocina/notificaciones` | Cocina, Admin, Gerente. Se calculan en el momento (no se guardan): el panel las consulta cada ~10 s. Tipos: `plato_sin_insumos` (plato en carta que no se puede preparar, con los insumos que faltan), `insumo_critico` (insumo agotado o en nivel crítico) y `se_puede_reactivar` (plato agotado a mano por Cocina que ya tiene insumos). Cada una trae `severidad` (`urgente` / `aviso` / `info`), `mensaje` y los datos del plato o insumo; `resumen` cuenta por tipo y severidad. Ver «Stock (hito 3)» |
| **Elaboraciones** | `/api/v1/elaboraciones` | Recetas que cocinan un **insumo propio** (salsa, masa, caldo) a partir de otros: `{"insumo": 4, "rinde": 1000, "dias_vencimiento": 3, "ingredientes": [{"insumo": 1, "cantidad": 800}, {"insumo": 3, "cantidad": 50}]}`. `rinde` es lo que sale de UNA tanda (unidad base del insumo producido); un ingrediente puede ser otra elaboración (sin ciclos: `400`). Un insumo tiene una sola elaboración y no se puede cambiar. Lectura: Cocina, Admin, Gerente (Cocina ve `tandas_posibles` sin costos; Admin/Gerente `costo_tanda` y `costo_por_unidad_base`); escritura: Admin, Gerente. `DELETE` da `409` si ya se produjo. No se mezclan con `/recetas` (esas son las de los platos) y no se pueden asignar a un producto. Ver «Stock (hito 6)» |
| **Producciones** | `POST` · `GET /api/v1/producciones` · `GET /api/v1/producciones/{id}` | Cocina, Admin, Gerente. `{"elaboracion": 1, "tandas": 2, "nota": "...", "fecha_vencimiento": "AAAA-MM-DD"}` (`tandas` 1 y `fecha_vencimiento` opcionales; sin fecha usa los `dias_vencimiento` de la elaboración). Descuenta los ingredientes por FEFO y da de alta el lote producido con **costo real**. Todo o nada (`409` si un ingrediente no alcanza; `400` si las tandas darían fracciones de algo que se cuenta en unidades). El costo solo lo ven Admin y Gerente. Filtros: `?insumo=`, `?elaboracion=`, `?desde=`, `?hasta=`, `?limite=` |
| **Vencimientos** | `GET /api/v1/vencimientos` · `POST /api/v1/vencimientos/procesar` | Cocina, Admin, Gerente. El GET lista los lotes ya vencidos (falta darlos de baja) y los que vencen dentro de los días de aviso, con `dias_restantes` y `texto` («vence en 2 dias»), el que vence antes primero; Admin/Gerente además el `valor`. El POST es el botón manual: da de baja los vencidos como pérdida con motivo `vencimiento` (también se hace solo al abrir cada jornada) |
| Configuración del stock | `GET` · `PUT /api/v1/configuracion/stock` | Admin, Gerente. `{"dias_aviso_vencimiento": 5}` (0 a 365): días de aviso **generales**, los que usa todo insumo que no tenga los suyos (`PUT /insumos/{id}` con `dias_aviso_vencimiento`) |
| **Lista de reposición** | `GET /api/v1/stock/reposicion` | Admin, Gerente. Qué **comprar** (agrupado por proveedor principal, con costo estimado a la última compra) y qué **elaborar** (con las tandas necesarias) para volver al stock objetivo. Por defecto solo agotados, críticos y bajos; `?todos=true` incluye cualquiera por debajo de su objetivo. Cuenta solo el **stock útil** (sin lo vencido ni lo que vence dentro del aviso de su insumo) y verifica que alcancen los ingredientes de cada elaboración: lo que falte se suma a lo que hay que comprar (ver «Stock (hito 6.1)») |
| **Pérdidas** | `POST` · `GET /api/v1/perdidas` · `GET /api/v1/perdidas/{id}` | Cocina, Admin, Gerente. Registra la pérdida de un **insumo** (`{"tipo": "insumo", "insumo": 1, "cantidad": 250, "motivo": "rotura_derrame", "nota": "..."}`, cantidad en unidad base) o de un **plato ya cocinado** (`{"tipo": "plato", "producto": 5, "cantidad": 2, "motivo": "error_cocina"}`: salen del stock los insumos de su receta). Descuenta por FEFO, todo o nada (`409` si el stock registrado no alcanza). El valor (`valor`, `valor_completo`) y los costos de cada lote solo los ven Admin y Gerente. Filtros del listado: `?tipo=insumo\|plato`, `?motivo=`, `?insumo=`, `?producto=`, `?desde=`, `?hasta=`, `?limite=`. El detalle trae de qué insumos y lotes salió. Ver «Stock (hito 4)» |
| Motivos de pérdida | `GET /api/v1/perdidas/motivos` | Cocina, Admin, Gerente. La lista cerrada (`codigo`, `etiqueta`, `requiere_nota`) para armar el desplegable |
| Resumen de pérdidas | `GET /api/v1/perdidas/resumen` | Admin, Gerente. Total valorizado, reparto por motivo (con el % del valor que explica cada uno), reparto insumo/plato e items que más pierden. Filtros `?desde=`, `?hasta=`, `?limite_items=` |
| Detalle de pedidos | `/api/v1/detalles-pedido` | Solo GET (los renglones los crea el worker al aceptar una comanda; no se editan a mano) |
| **Comandas (cliente)** | `POST /api/v1/pedidos` | Crea una comanda, la encola en RabbitMQ (`202 Accepted`). Exige el `pin` de la mesa en el cuerpo: `{"id_comanda_uuid": "...", "mesa_id": 2, "pin": "4821", "items": [{"id": 1}, {"id": 2, "sin": [7]}], "version_menu": 25}` (`sin` es opcional: ids de los insumos que el cliente pide quitar de ese plato; solo se puede quitar lo que la receta marcó como `quitable`, ver «Stock (hito 5)». `version_menu` es opcional: la versión del menú que el cliente tenía; ver «El cliente paga el precio que vio». `comensal` es opcional: el nombre de quien pide, para la cuenta; `compartido` es opcional por plato: lista de 2 o más nombres entre quienes se divide, ver «Cobros (hito 3)»). `409` si la mesa no tiene sesión abierta, `409` si la cuenta de la mesa ya está en curso (factura emitida), `403` si el PIN no coincide. `409` con `modificadores_invalidos` (`id`, `nombre`, `insumo`, `motivo`) si se pide quitar algo que no se puede. `409` con `productos_sin_stock` (`id`, `nombre`, `pedido`, `posibles`) y un `error` listo para mostrar si los insumos no alcanzan para todo el pedido: se rechaza el pedido entero (ver «Stock (hito 2)») |
| **Tablero de cocina** | `GET /api/v1/pedidos` | Lista las comandas activas con su estado (lee de SQL Server + Redis) |
| **Avance de estado** | `PATCH /api/v1/pedidos/{uuid}/estado` | Cambia el estado de una comanda (`pendiente`/`proceso`/`listo`/`entregado`) |
| **Comprobante PDF** | `GET /api/v1/pedidos/{uuid}/ticket` | Descarga el comprobante generado de forma asíncrona |
| **Cotizaciones** | `GET /api/v1/cotizaciones` | Público. Las tres monedas (`USD`, `BRL`, `PYG`) con su cotización vigente: `valor` = pesos por 1 unidad de la moneda, `fecha` (día al que corresponde), `actualizada_en` y `fuente` (`BCRA`). `valor` es `null` si todavía no se guardó ninguna. `desactualizada` avisa si hace más de 2 horas que no se consulta al BCRA con éxito. Ver «Cobros (hito 1)» |
| Actualizar cotizaciones | `POST /api/v1/cotizaciones/actualizar` | Admin, Gerente. Consulta al BCRA ahora (no se carga ningún valor a mano) y guarda lo que cambió: `guardadas` y `sin_cambios`. `502` si no se pudo consultar; siguen vigentes las últimas guardadas (el Gerente además ve `ultimo_error`) |
| Caja actual | `GET /api/v1/caja/actual` | Mozo, Admin, Gerente. El mozo solo ve `abierta` (sin caja abierta no se puede cobrar); Admin y Gerente ven además la caja con su arqueo por moneda. Ver «Cobros (hito 2)» |
| Abrir caja | `POST /api/v1/caja/abrir` | Admin, Gerente. `{"montos": {"ARS": 10000, "USD": 50}}` (opcional; lo que falta arranca en 0). `409` si ya hay una abierta. No necesita jornada abierta |
| Cerrar caja | `POST /api/v1/caja/cerrar` | Admin, Gerente. `{"montos": {"ARS": .., "USD": .., "BRL": .., "PYG": ..}, "mercado_pago": 15000}`: lo contado en el cajón (las cuatro monedas, 0 si no hay) y lo acreditado en la cuenta de Mercado Pago (obligatorio si el sistema registró cobros digitales). Devuelve esperado, informado y diferencia por medio, el total en pesos y `advertencias` si hay faltante o sobrante (no impide cerrar) |
| Movimientos de caja | `GET` / `POST /api/v1/caja/movimientos` | Admin, Gerente. GET: los de la caja abierta. POST: `{"tipo": "Ingreso" o "Egreso", "moneda": "ARS", "monto": 500, "descripcion": "..."}`; la descripción es obligatoria y un egreso no puede sacar más efectivo del que hay en esa moneda (`409`) |
| Historial de cajas | `GET /api/v1/cajas`, `GET /api/v1/cajas/{id}` | Admin, Gerente. Filtros `?estado=Abierta` o `Cerrada` y `?fecha=AAAA-MM-DD`. El detalle trae el arqueo y todos los movimientos |
| Cuenta de la mesa | `GET /api/v1/sesiones-mesa/{id}/cuenta` | Mozo (solo sus mesas), Admin, Gerente. Sin factura es una vista previa del consumo; con factura, lo congelado al emitirla. Trae `total`, `saldo`, `equivalentes` (USD, BRL, PYG), `renglones`, `por_comensal` (informativo), `pagos`, `puede_cobrarse`, `pedidos_en_cocina`, `en_sobremesa` y `caja_abierta`. Todos los importes son texto (`"10000.00"`) |
| Emitir factura | `POST /api/v1/sesiones-mesa/{id}/factura` | Mozo (sus mesas), Admin, Gerente. Congela el consumo y avisa que la mesa ya no pide. `201`; si ya hay una vigente la devuelve (`200`). `409` sin caja abierta o sin consumo |
| Cobrar en efectivo | `POST /api/v1/facturas/{id}/pagos/efectivo` | Mozo (sus mesas), Admin, Gerente. `{"moneda": "USD", "recibido": 20, "propina": 1500, "monto_cuenta": 20000, "clave": "..."}`. Una moneda por cobro; la cotización vigente se congela en el pago; el vuelto es siempre en pesos; la propina (opcional, en pesos) va al mozo de la mesa. `clave` evita cobrar dos veces si se reintenta (`200` con el mismo pago). `409` si no hay caja, hay pedidos en preparación o falta efectivo en pesos para el vuelto |
| Factura | `GET /api/v1/facturas/{id}` · `GET /api/v1/facturas` | El detalle: Mozo (sus mesas), Admin, Gerente. El listado (`?estado=Emitida\|Pagada\|Anulada`, `?fecha=AAAA-MM-DD`): Admin, Gerente |
| Anular un pago | `POST /api/v1/pagos/{id}/anular` | Admin, Gerente. `{"motivo": "..."}` obligatorio. Solo pagos en efectivo: devuelve el efectivo (contramovimiento en la caja) y reabre el saldo |
| Anular una factura | `POST /api/v1/facturas/{id}/anular` | Admin, Gerente. `{"motivo": "..."}` obligatorio. Solo sin pagos aprobados ni pendientes; la mesa vuelve a poder pedir |
| Propinas | `GET /api/v1/propinas` | Cada mozo ve las suyas; Admin y Gerente las de todos (`?mozo=id`). Filtros `?desde` y `?hasta` (AAAA-MM-DD) |
| Pagar con Mercado Pago (cliente) | `POST /api/v1/cuenta/pagar/mercadopago` | Público con el PIN de la mesa: `{"numero_mesa": 5, "pin": "1234", "monto_cuenta": 8000, "propina": 800, "clave": "..."}` (`monto_cuenta`, `propina` y `clave` opcionales; sin `monto_cuenta` paga todo el saldo). Emite la factura si no había y devuelve `pago.url_pago`, el link al que se redirige al cliente, y la cuenta. `201` si creó el pago, `200` si ya había uno pendiente (mismo link). `409` si no hay caja abierta, hay pedidos en preparación o la cuenta ya está cubierta; `400` si el monto o la propina son inválidos; `502` si Mercado Pago no responde |
| Estado del pago (cliente) | `POST /api/v1/cuenta/pagar/estado` | Público con el PIN: `{"numero_mesa": 5, "pin": "1234", "pago": 12}`. Confirma con Mercado Pago y devuelve el pago y la cuenta (con `aviso` si Mercado Pago no respondió y se muestra lo último conocido) |
| Cancelar el pago (cliente) | `POST /api/v1/cuenta/pagar/cancelar` | Público con el PIN, mismo cuerpo. Solo cancela si Mercado Pago confirma que no se pagó (y deja vencido el link); `409` si hay un pago en proceso |
| Sincronizar un pago | `POST /api/v1/pagos/{id}/sincronizar` | Mozo (sus mesas), Admin, Gerente. Confirma con Mercado Pago ahora (el worker lo hace solo). Devuelve el pago y la cuenta |
| Cancelar un pago | `POST /api/v1/pagos/{id}/cancelar` | Admin, Gerente. `{"motivo": "..."}` obligatorio. Solo si Mercado Pago confirma que no se pagó |
| Simular el pago del cliente | `POST /api/v1/pagos/{id}/simular` | Admin, Gerente, **solo con `MP_MODO=simulado`** (si no, `404`). `{"resultado": "approved" \| "rejected" \| "in_process", "monto": 8800}` (`monto` opcional, para probar un monto distinto). Hace de «el cliente pagó el link» en las pruebas |
| Cuenta del cliente | `POST /api/v1/cuenta` | Público con el PIN de la mesa: `{"numero_mesa": 5, "pin": "1234"}`. Total, equivalentes, consumo por comensal, pagos y saldo (sin nombres del personal) |
| **Pedir la factura (cliente)** | `POST /api/v1/cuenta/factura` | Público con el PIN: `{"numero_mesa": 5, "pin": "1234", "quiere_factura": true, "nombre_factura": "David"}`. Tilda o destilda la casilla «quiero factura» una vez emitida la factura (si no, la casilla viaja al pagar: ver «Cobros (hito 6)»). `400` si se tilda sin nombre; `409` si todavía no hay factura emitida |
| **Comprobante PDF (cliente)** | `POST /api/v1/cuenta/comprobante` | Público con el PIN en el cuerpo (no en la URL): devuelve el PDF de la factura. El nombre del archivo viene en `Content-Disposition` (`David - 08-11-26.pdf`); `"descargar": true` lo marca como adjunto. `409` si no se pidió la factura o la cuenta todavía no está pagada |
| **Comprobante PDF (personal)** | `GET` · `PATCH /api/v1/facturas/{id}/comprobante` | Mozo (solo sus mesas), Admin, Gerente. `GET` baja el PDF (`?descargar=1` fuerza la descarga); `PATCH {"quiere_factura": true, "nombre_factura": "David"}` cambia la casilla. Mismos `409` que arriba; `404` si no existe o no es de su mesa |
| **Auditoría** | `GET /api/v1/auditoria` | Admin, Gerente. Línea de tiempo de cobros, de lo más nuevo a lo más viejo: cada cambio de un pago, cada ingreso o egreso de caja, aperturas y cierres de caja, emisión y anulación de facturas y cierres de mesa forzados. Filtros: `desde`, `hasta` (AAAA-MM-DD, ambos incluidos), `tipo` (`pago`, `movimiento`, `caja`, `factura`, `mesa`; varios con coma), `empleado`, `mesa` (número), `caja`, `factura`, `pago`, `limite` (100 por defecto, máx. 500) y `desplazamiento`. Ver «Cobros (hito 6)» |

## Autenticación y permisos

Los endpoints protegidos exigen el encabezado `Authorization: Bearer <token>`. Sin token responden `401`; con token de un rol sin permiso, `403`. El rol y el estado del empleado se consultan en la base en cada pedido: una baja o un cambio de rol rige de inmediato.

| Recurso | Lectura (GET) | Escritura (POST / PATCH / DELETE) |
|---|---|---|
| Menú (`productos`, `categorias`) | Público | Admin, Gerente |
| Imagen de producto | Público | Admin, Gerente |
| Mesas | Mozo, Admin, Gerente | Admin, Gerente |
| Roles y empleados | Gerente | Gerente (el DELETE es baja lógica; no puede darse de baja ni cambiarse el rol a sí mismo, y debe quedar al menos un Gerente activo) |
| Abrir / cerrar mesa | Mozo, Admin, Gerente | Mozo, Admin, Gerente (un Mozo solo ve y cierra sus propias sesiones; forzar el cierre con saldo: Admin, Gerente) |
| Detalle de pedido (`/detalles-pedido`) | Mozo, Admin, Gerente | — (solo lectura) |
| Cuenta de una mesa, emitir factura, cobrar en efectivo, detalle de factura, propinas | Mozo (solo sus mesas y sus propinas), Admin, Gerente | Mozo, Admin, Gerente |
| Listado de facturas, anular pago, anular factura | Admin, Gerente | Admin, Gerente |
| Sincronizar un pago de Mercado Pago | — | Mozo (solo sus mesas), Admin, Gerente |
| Cancelar un pago de Mercado Pago, simular el pago (modo simulado) | — | Admin, Gerente |
| Pagar, consultar y cancelar con Mercado Pago (`/cuenta/pagar/...`) | — | Público, protegido por el PIN de la mesa |
| Cuenta del cliente (`POST /cuenta`) | — | Público, protegido por el PIN de la mesa |
| Comprobante PDF de la factura (`/facturas/{id}/comprobante`) | Mozo (solo sus mesas), Admin, Gerente | Mozo (solo sus mesas), Admin, Gerente |
| Pedir la factura y bajar el comprobante (`/cuenta/factura`, `/cuenta/comprobante`) | — | Público, protegido por el PIN de la mesa |
| Auditoría (`GET /auditoria`) | Admin, Gerente | — |
| Turnos (horarios de atención) | Público | Gerente |
| Estado de la jornada (`GET /jornada/actual`), especiales (calendario, vigentes) | Público | — |
| Abrir / cerrar jornada, historial de jornadas | Admin, Gerente | Admin, Gerente |
| Especiales (crear, editar, borrar, fechas puntuales) | Público | Admin, Gerente |
| Proveedores, insumos, compras, lotes, movimientos y ajustes de stock | Admin, Gerente | Admin, Gerente |
| Estado del stock (`GET /stock`) | Cocina, Admin, Gerente (Cocina no ve costos ni proveedores) | — |
| Recetas | Cocina, Admin, Gerente (Cocina no ve costos ni márgenes) | Admin, Gerente |
| Extras de una receta (`/recetas/{id}/extras`, `/extras/{id}`) | Cocina, Admin, Gerente | Admin, Gerente |
| Productos sin receta, comandas rechazadas | Admin, Gerente | — |
| Notificaciones de Cocina (`GET /cocina/notificaciones`) | Cocina, Admin, Gerente | — |
| Elaboraciones (`/elaboraciones`) | Cocina, Admin, Gerente (Cocina no ve costos) | Admin, Gerente |
| Producciones (`/producciones`) y vencimientos (`/vencimientos`) | Cocina, Admin, Gerente (Cocina no ve costos ni valores) | Cocina, Admin, Gerente |
| Configuración del stock (`/configuracion/stock`) y lista de reposición (`/stock/reposicion`) | Admin, Gerente | Admin, Gerente |
| Pérdidas y sus motivos (`/perdidas`) | Cocina, Admin, Gerente (Cocina no ve valores ni costos) | Cocina, Admin, Gerente |
| Resumen de pérdidas (`/perdidas/resumen`) | Admin, Gerente | — |
| Tablero de cocina (`GET /pedidos`, `/cocina/tablero`) | Cocina, Mozo, Admin, Gerente (el mozo arma con esto sus avisos) | — |
| Cambio de estado de comanda (`PATCH /pedidos/{uuid}/estado`) | — | Cocina, Admin, Gerente |
| Tablero de la barra (`GET /barra/tablero`) y su cambio de estado (`PATCH /barra/pedidos/{uuid}/estado`) | Bartender, Admin, Gerente | Bartender, Admin, Gerente |
| Bebidas del mozo (`GET /mozo/bebidas`, `POST /pedidos/{uuid}/bebidas/entregar`) | Mozo (solo sus mesas), Admin, Gerente | Mozo (solo sus mesas), Admin, Gerente |
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

## Disponibilidad y aviso en tiempo real

- **Tres indicadores, tres dueños.** `activo` es la decisión de carta del Admin («Ocultar plato»). `disponible` lo calcula el stock (0 si faltan insumos). `agotado_manual` es el override de Cocina («sin insumos»). El cliente solo ve el plato si `activo` y `disponible` y no `agotado_manual` (el producto lo informa en `visible`). Separarlos evita que el stock automático pise una decisión del Admin o de Cocina.
- **Reactivación:** un plato agotado a mano **no se reactiva solo** al reponer insumos. Alguien con rol Cocina, Admin o Gerente lo reactiva (`POST /productos/{id}/reactivar`), y el sistema no lo permite mientras el stock no alcance. Cuando el stock vuelva a alcanzar, el sistema avisa con una alerta que se puede reactivar (se agrega con el stock).
- **Menú:** `GET /productos` (cliente) solo trae lo visible. `GET /productos?incluir_inactivos=true` es la vista de gestión: trae todo con los indicadores (`activo`, `disponible`, `agotado_manual`, `visible`, `agotado_por`).
- **Garantía en el servidor:** `POST /pedidos` responde `409` con `productos_no_disponibles: [{id, nombre, motivo}]` (`sin_insumos`, `fuera_de_carta` o `no_existe`) si algún plato ya no se puede pedir, aunque la pantalla del cliente esté desactualizada. Ese es el control que impide vender lo que no hay; el aviso en tiempo real es para que la pantalla se entere sola.
- **Aviso en tiempo real (SSE):** cada cambio del menú sube un contador de **versión** en Redis y avisa por pub/sub. Cuenta cualquier edición de un producto (precio, foto, descripción, categoría, alta, baja, activar/desactivar), de una categoría, de los especiales, de la jornada y de la disponibilidad. El cache del listado guarda cada copia bajo una clave con esa versión, así tras un cambio nunca se sirve una copia vieja. `GET /catalogo/eventos` mantiene una conexión abierta y manda `event: catalogo` con la versión. El front, ante una versión distinta de la que tiene, vuelve a pedir `/productos`.
  - *Basado en estado:* al conectar siempre se manda la versión actual, así un cliente que estuvo desconectado se entera de lo que se perdió.
  - *Robusto:* latido cada 15 s, la conexión se renueva sola a los 5 min, tope de 300 conexiones (60 por IP; pasado el tope, o si Redis no responde al conectar, responde `503` y el front usa `/catalogo/version`), y si Redis cae con el flujo ya abierto, este termina limpio y el navegador reintenta solo.
  - *Contrato para el front:* usar `EventSource` y, si `onerror` deja la conexión cerrada (`readyState === 2`), consultar `/catalogo/version` cada 5 s y reintentar el SSE cada 30 s. Al recibir un evento, esperar un tiempo aleatorio de 0 a 300 ms antes de pedir `/productos` (evita que todos los clientes pidan a la vez). El navegador permite pocas conexiones SSE por sitio: abrir una sola por pestaña.
  - *Despliegue:* con `runserver` cada conexión ocupa un hilo (alcanza para la demo). En producción conviene un servidor ASGI.
- **El cliente paga el precio que vio.** `GET /productos` devuelve en el encabezado `X-Catalogo-Version` la versión del menú que está mostrando (el especial vigente cuenta como precio). El front la guarda y la manda como `version_menu` en `POST /pedidos`. El servidor recuerda qué precio mostraba cada versión (2 h después de un cambio, 24 h la vigente) y cobra ese precio aunque haya subido mientras el cliente armaba el pedido; si bajó, cobra el nuevo. **El cliente nunca manda un precio**, solo la versión: no hay forma de elegir un precio inventado. Sin `version_menu`, o con una versión desconocida o vencida, se cobra el precio vigente. Los platos agotados o fuera de carta se rechazan igual (`409`), sin importar el precio.
- **Probarlo:** `python Tests\Scripts\probar_sse.py` (con el servidor corriendo) mide cuánto tarda el aviso, comprueba la reconexión y deja el plato reactivado. La colección de Postman tiene la carpeta «4. Disponibilidad».

## Stock (hito 1)

Cómo se conecta todo, en el orden en que se usa:

1. **Proveedores** (contacto, teléfono, email) y **insumos** (la materia prima). Cada insumo se mide en una *unidad base* según su tipo: `Masa` = gramos, `Volumen` = mililitros, `Unidad` = unidades. Kilos y litros son solo una forma de mostrarlos. A cada insumo se le asocian uno o varios proveedores, uno de ellos principal.
2. **Compra → lotes.** Cada línea de una compra crea un *lote*: lo que entró de ese insumo, con su costo por unidad base y su vencimiento. El tamaño de la bolsa se define en cada compra (10 bolsas de 15 kg un mes, de 10 kg otro). El stock de un insumo es la **suma de sus lotes activos**; no hay una columna con el total. El costo de reposición es el del último lote comprado.
3. **Todo movimiento queda en el libro** (`MovimientoStock`): cantidad con signo, lote, tipo (`Compra`, `Consumo`, `Perdida`, `Ajuste`, `Devolucion`, `Vencido`, `Elaboracion`), quién, en qué jornada y por qué comanda. Nunca se edita ni se borra; un error se corrige con otro movimiento. La suma de los movimientos de un lote siempre es igual a su cantidad actual (`GET /stock/verificacion`).
4. **Descuento FEFO:** siempre se saca del lote que vence antes (los que no vencen, al final). No existe stock negativo: la base lo impide con un `CHECK`, y cada operación bloquea los lotes que toca para que dos operaciones simultáneas se ordenen.
5. **Semáforo por insumo.** El porcentaje es el stock actual sobre el *stock objetivo* del insumo; amarillo (`Bajo`) a partir del umbral bajo (50 % por defecto) y rojo (`Critico`) a partir del umbral crítico (20 %); `Agotado` si no queda nada y `SinObjetivo` si no se definió el 100 %. **No hay un porcentaje general**: se muestra cada insumo y se ordena por gravedad, porque un promedio taparía un insumo esencial en rojo. `resumen` cuenta cuántos insumos hay en cada estado.
6. **Próximos hitos:** disponibilidad de los platos según el stock, pérdidas con motivo, modificadores, y elaboración (sub-recetas), vencimientos y alertas. Las recetas y el descuento por comanda son el hito 2 (abajo).

- **Probarlo:** la carpeta «5. Stock» de la colección de Postman (requiere los scripts SQL 08 a 11). Deja sus datos de prueba dados de baja; los lotes y movimientos quedan en el libro porque no se borran.

## Stock (hito 2): recetas y descuento por comanda

La rueda sigue donde terminaba el hito 1: **receta → pedido → descuento**.

1. **Receta.** Es una entidad propia: dice cuánto de cada insumo gasta **una unidad vendida** (en unidad base: g, ml o u). Se crea una sola vez y los productos del menú la referencian (`PUT /productos/{id}/receta`), así que no se duplican datos: dos platos pueden compartir una receta y cada uno conserva su precio, descripción y porciones. Un producto **sin receta no lleva control de stock** y siempre se puede pedir (una bebida que se vende cerrada); `GET /productos-sin-receta` lista esos productos para que el Gerente no se olvide de ninguno. La receta es interna: el menú público no la muestra. (El «rinde» —una olla que da 20 porciones— llega con las sub-recetas, hito 6.)
2. **Costo del plato** = Σ cantidad × costo de reposición (último lote comprado) de cada ingrediente. Lo ven Admin y Gerente, junto con el margen de cada producto; Cocina ve cantidades y cuántas porciones se pueden preparar. Si algún insumo nunca se compró, `costo_completo` es `false` y el costo es parcial.
3. **Aviso previo en el carrito.** `POST /pedidos` calcula, con el stock de ese momento, cuántas unidades alcanzan de cada plato (dos platos que comparten un insumo no cuentan dos veces la misma cantidad). Si no alcanza, responde `409` y **rechaza el pedido entero** (no se manda nada a medias) con un mensaje genérico que no dice qué insumo falta: `Insumos insuficientes. Podemos preparar solamente 3 de 4 Tallarines. Disculpe las molestias.` (o `Por ahora no podemos preparar …` si no queda ni una). Los datos viajan también en `productos_sin_stock`.
4. **Descuento al llegar la comanda.** El worker, dentro de la misma transacción que crea los ítems, descuenta cada insumo por FEFO (movimientos de tipo `Consumo`, ligados a la comanda y a la jornada). Es todo o nada.
5. **Carrera por la última porción.** El aviso del carrito es solo eso, un aviso: dos clientes pueden ver la última porción a la vez. La palabra final la tiene el worker, que bloquea los lotes: **gana la comanda que llega primero y se rechaza la que llega después**. La rechazada queda registrada en `ComandaRecibida` (`Estado = 'Rechazada'`) con el motivo interno y el mensaje para el cliente, sin ítems y sin descontar nada; si RabbitMQ reentrega el mensaje, se reconoce por su UUID y no se procesa de nuevo. El cliente la ve en su historial como `rechazada`; no aparece en el tablero de Cocina.
6. **Disponibilidad automática:** es el hito 3 (abajo).

- **Probarlo:** la carpeta «6. Recetas y descuento por comanda» de la colección de Postman (requiere los scripts SQL 08 a 12 y el worker corriendo); `python Tests\Scripts\probar_recetas_calculos.py` (cálculos, no necesita nada corriendo) y `python Tests\Scripts\probar_rechazo_comanda.py` (la carrera por la última porción, de punta a punta; necesita servidor, worker, RabbitMQ y Redis).

## Stock (hito 3): disponibilidad de los platos y notificaciones de Cocina

1. **Regla:** *mientras haya stock para ofrecer 1 plato, el plato se ofrece.* Tiene que alcanzar para **una unidad completa de su receta**, nunca una fracción (una picada para 4 personas se ofrece solo si alcanza para la picada entera; el campo `Porciones` del producto son las personas que come y no interviene). Un producto sin receta no lleva control de stock y siempre se ofrece.
2. **Cuándo se recalcula:** en cada movimiento de stock (compra, ajuste, baja de lote y consumo del worker) para los platos cuya receta usa esos insumos, y cuando se edita una receta o se asigna/quita a un producto. Se hace con el stock ya confirmado en la base (después de la transacción) y escribe `Producto.Disponible`.
3. **Efecto en el menú:** si algún plato cambia, se avisa al menú del cliente por el aviso en tiempo real (el mismo de la disponibilidad): un plato desaparece apenas se acaba un insumo y vuelve apenas se repone. Con `incluir_inactivos=true` (vista de gestión) se ve con `disponible: false`. Un pedido que lo incluya recibe `409` con `motivo: "sin_insumos"`.
4. **Quién decide qué:** `Activo` es la carta (Admin/Gerente), `Disponible` lo calcula el stock y `AgotadoManual` es Cocina. Se ve en el menú solo si `Activo` y `Disponible` y no `AgotadoManual`. El stock **nunca** reactiva solo un plato que Cocina agotó a mano: solo avisa que se puede reactivar.
5. **Notificaciones de Cocina** (`GET /cocina/notificaciones`): no se guardan, se calculan del estado de ahora, porque son situaciones y no eventos; cuando se resuelven desaparecen solas y no hay nada que marcar como leído. Orden: lo urgente primero (platos antes que insumos), después avisos e info. Para el panel: consultar cada ~10 s y usar `resumen.total` (o `por_severidad.urgente`) para el numerito de la pestaña. Más adelante se suman vencimientos y pérdidas sin cambiar el formato.
6. **Limitación conocida:** si dos recálculos se cruzan en el mismo instante, el último en leer gana; el siguiente movimiento de stock lo corrige.

- **Probarlo:** la carpeta «6» de la colección de Postman (hitos 2 y 3) y `python Tests\Scripts\probar_recetas_calculos.py` (incluye los cálculos de disponibilidad y notificaciones).

## Stock (hito 4): pérdidas con motivo

1. **Qué se puede perder:** un **insumo** (se venció, se derramó, se rompió: sale la cantidad indicada) o un **plato ya cocinado** (se quemó, se cayó, volvió de la mesa: salen del stock los insumos de su receta, por cada unidad perdida). Un plato sin receta no se puede registrar (no hay insumos que descontar). Las bajas de lote del hito 1 también quedan registradas como pérdidas de insumo.
2. **Motivo de lista cerrada** (`GET /perdidas/motivos`): `vencimiento`, `rotura_derrame`, `error_cocina`, `devolucion_cliente`, `consumo_personal` y `otro`. Es cerrada a propósito: con texto libre después no se podría agrupar para saber dónde y por qué se pierde más. `otro` exige una `nota` que explique qué pasó; en los demás es opcional. Un motivo nuevo se agrega en `stock_calculos.MOTIVOS_PERDIDA` y en el `CHECK` de la tabla `Perdida` (script 13).
3. **Quién:** Cocina las carga (es quien presencia la pérdida) y puede consultarlas, pero **no ve valores ni costos**. Admin y Gerente ven el valor de cada pérdida y el resumen.
4. **Cómo se valoriza:** el descuento es FEFO, así que cada pérdida sale de lotes concretos y se valoriza al **costo real de esos lotes**. El valor no se guarda: se calcula desde el libro de movimientos (cada movimiento apunta a su pérdida por `MovimientoStock.IdPerdida`), así nunca hay un promedio general ni un precio desactualizado. `valor_completo: false` avisa que algún lote no tiene costo (insumo que nunca se compró) y el valor queda por debajo del real.
5. **Todo o nada:** si el stock registrado no alcanza, `409` y no se modifica nada (ni la pérdida ni el stock). Un error de carga no se borra: se corrige con un ajuste de stock. Las pérdidas, como el libro, no se editan ni se borran.
6. **Efecto en el menú:** una pérdida es un movimiento de stock más, así que recalcula la disponibilidad de los platos (hito 3): si deja a un plato sin insumos, desaparece del menú.
7. **Resumen** (`GET /perdidas/resumen`, Admin y Gerente): total, reparto por motivo con el porcentaje del **valor perdido** que explica cada uno (no es un promedio), reparto insumo/plato y los items que más pierden.
8. **Diferencia con el ajuste:** el ajuste (Admin y Gerente) corrige el stock cuando el conteo físico no coincide con el sistema, sin una causa conocida; la pérdida registra un hecho concreto con su motivo.

- **Probarlo:** la carpeta «7. Pérdidas con motivo» de la colección de Postman (requiere los scripts SQL 08 a 13 y el worker corriendo) y `python Tests\Scripts\probar_perdidas_calculos.py` (cálculos, no necesita nada corriendo).

## Stock (hito 5): modificadores («sin cebolla»)

1. **Qué se puede pedir:** quitar ingredientes de un plato. En el pedido, cada item admite `"sin": [id_insumo, ...]`: `{"id": 12, "sin": [7]}`. Si se omite, el item es igual que antes. Por ahora solo «sin X»; los extras («con doble queso») quedan para cuando estén los cobros, porque cambian el precio.
2. **Qué se puede quitar:** solo lo que Admin o Gerente marcó como `quitable` en la receta (`"quitable": true` en cada ingrediente). Una receta no puede tener todos sus ingredientes quitables: al menos uno es fijo, así el plato nunca queda vacío. Si el pedido trae algo que no se puede quitar: `409` con `modificadores_invalidos` y nada se encola.
3. **Precio:** no cambia. Quitar un ingrediente no baja el precio.
4. **Menú:** cada producto trae `quitables` (`[{"id": 7, "nombre": "Cebolla"}]`, vacío si no ofrece nada). Solo id y nombre del insumo: el menú sigue sin mostrar cantidades ni recetas. El cache del menú se invalida solo cuando cambia lo quitable de un plato.
5. **Stock:** se descuenta la receta **sin** los ingredientes quitados. Dos renglones del mismo plato con distintos «sin» son renglones distintos (1 común y 2 sin cebolla = 2 renglones). La validación previa del pedido y el worker usan la misma cuenta, así que «3 comunes» puede dar `409` mientras «3 sin cebolla» pasa.
6. **Dónde se ve:** el tablero de Cocina, el historial de la mesa y el ticket en PDF muestran el campo `sin` (nombres de los ingredientes quitados).
7. **Por qué una tabla aparte (`PedidoDetalleModificador`):** lo quitado es una lista que se repite por renglón; guardarla como texto en `PedidoDetalle` rompería la primera forma normal y no permitiría integridad referencial ni reportes («cuánta cebolla se dejó de gastar»). Cuando exista el comensal, hereda de su renglón.
8. **Limitación conocida:** la disponibilidad del menú usa la receta **completa** (regla del hito 3). Si se acaba un ingrediente quitable, el plato desaparece aunque podría servirse «sin» ese ingrediente.

- **Probarlo:** la carpeta «8. Modificadores» de la colección de Postman (requiere los scripts SQL 08 a 14 y el worker corriendo) y `python Tests\Scripts\probar_modificadores_calculos.py` (cálculos, no necesita nada corriendo). La carpeta entrega los pedidos que crea, así no deja restos en el tablero de Cocina.

## Stock (hito 6): elaboraciones, vencimientos, alertas y reposición

1. **Elaboraciones (sub-recetas con rinde):** una elaboración es una receta que cocina un **insumo propio** (salsa de tomate, masa, caldo) a partir de otros insumos. `rinde` dice cuánto sale de UNA tanda. Un ingrediente puede ser a su vez otra elaboración (por ejemplo, una salsa picante hecha con la salsa base): se permiten todos los niveles que haga falta y solo se rechazan los **ciclos** (una elaboración que, directa o indirectamente, necesita de sí misma). Los platos usan el insumo elaborado como cualquier otro, y el stock de platos funciona igual.
2. **Producir:** Cocina registra cuántas tandas hizo (`POST /producciones`). En una sola transacción: se descuentan los ingredientes por FEFO, entra un lote nuevo del insumo producido (origen `Elaboracion`, con vencimiento a los `dias_vencimiento` de la elaboración si los tiene) y todo queda en el libro (`Consumo` negativo por cada ingrediente y `Elaboracion` positivo por el lote, enlazados por `MovimientoStock.IdProduccion`). Todo o nada: si falta un ingrediente, `409` y no se toca nada. No se produce solo ni se arrastra un faltante: para hacer la salsa picante, la salsa base tiene que estar producida antes.
3. **Costo real, sin promedios:** el costo por gramo del lote producido es lo que costaron los lotes que se consumieron (cada uno a su costo) dividido lo que salió. Un plato hecho con salsa elaborada hereda ese costo. `ultimo_costo` (costo de reposición de recetas y márgenes) ahora también mira los lotes de elaboración. Solo Admin y Gerente ven costos.
4. **Unidades enteras:** lo que se cuenta en unidades no se parte. Si las tandas darían medio huevo (o medio producto), `400` con el motivo; en gramos o mililitros las fracciones (media tanda) están bien.
5. **Vencimientos:** un lote se puede usar hasta el día de su vencimiento inclusive; al día siguiente está vencido. Los vencidos se dan de baja como **pérdida con motivo `vencimiento`** al costo real del lote (queda en el libro y en `/perdidas`), de dos formas: **automáticamente al abrir cada jornada** (la respuesta de `POST /jornada/abrir` trae `vencimientos` con lo dado de baja, lo que está por vencer y `avisos` listos para mostrar) y con el **botón manual** `POST /vencimientos/procesar`. Si el proceso automático falla, la jornada igual se abre (`vencimientos: null`) y el botón lo repite.
6. **Aviso con días de anticipación:** se avisa de los lotes que vencen dentro de `dias_aviso_vencimiento` días (5 por defecto; Admin y Gerente lo cambian con `PUT /configuracion/stock`). Los días restantes se recalculan en cada consulta: el aviso de la apertura de cada jornada y las notificaciones de Cocina siempre muestran cuánto falta.
7. **Alertas nuevas** en `GET /cocina/notificaciones`: `lote_vencido` (urgente; falta darlo de baja), `lote_por_vencer` (aviso; urgente si vence hoy) y `elaboracion_a_producir` (elaboración agotada, crítica o baja, con `tandas_sugeridas`). Las elaboraciones ya no salen duplicadas como `insumo_critico`.
8. **Lista de reposición** (`GET /stock/reposicion`, Admin y Gerente): para cada insumo agotado, crítico o bajo, cuánto falta para llegar al objetivo. Lo que se compra va agrupado por proveedor principal con el costo estimado a la última compra (`completo: false` si algún insumo nunca se compró); lo que se elabora va aparte con las tandas necesarias.
9. **Limitaciones conocidas:** las del hito 6 que se resolvieron en el 6.1 (aviso por insumo y reposición con stock útil) están en la sección siguiente.

- **Probarlo:** la carpeta «9. Elaboraciones, vencimientos y reposición» de la colección de Postman (requiere los scripts SQL 08 a 16 y el worker corriendo), `python Tests\Scripts\probar_elaboraciones_calculos.py` (cálculos, no necesita nada corriendo) y `python Tests\Scripts\probar_vencimientos.py` (con el entorno virtual activo; crea lotes ya vencidos directo en la base, porque la API no deja cargarlos, y prueba la baja automática de la apertura).

## Stock (hito 6.1): aviso por insumo y reposición confiable

1. **Aviso de vencimiento por insumo:** cada insumo puede tener sus propios `dias_aviso_vencimiento` (el tomate avisa 2 días antes; la harina, 30). Si no los tiene (`null`), usa los generales de `/configuracion/stock` (5 por defecto). Se cambian con `PUT`/`PATCH /insumos/{id}` (Admin y Gerente); `null` vuelve a los generales y `0` avisa recién el día que vence. No se guarda nada en los lotes: el aviso se calcula en cada consulta con el valor actual del insumo, así que **un cambio afecta al instante a todos sus lotes**, los que ya hay y los que entren. Cada fila de `/vencimientos` y de las notificaciones dice con cuántos días se avisó (`dias_aviso`), y `aviso_propio` si son los del insumo. El aviso de la apertura de jornada usa lo mismo. El aviso se mide por **lote**: un paquete mayorista con una misma fecha es un lote; si una entrega trae bolsas con fechas distintas, se cargan como renglones separados de la compra.
2. **Reposición con stock útil:** lo que ya venció (y todavía no se dio de baja) o vence dentro de la ventana de aviso de su insumo **no se cuenta como stock**, porque no se va a poder usar. Con 10 kg de harina y 6 kg que vencen en 3 días, la reposición ve 4 kg útiles: el estado (`Bajo`, `Crítico`…) y lo que falta para el objetivo se calculan con esos 4 kg. Cada ítem trae `stock`, `a_perder`, `stock_util` y sus textos. Es una regla conservadora a propósito: quien quiere ser menos estricto baja los días de aviso de ese insumo.
3. **Elaborar necesita ingredientes:** para cada elaboración que hay que producir (por estar baja, o porque otra elaboración la necesita) se verifica que alcancen los ingredientes **con lo que se puede usar hoy** (lo ya vencido no sirve; lo que recién va a vencer todavía sí). Cada ítem de `producir` trae `tandas`, `cantidad_a_producir`, `tandas_posibles` (las que alcanzan hoy), `alcanza` e `ingredientes_faltantes` (cuánto se necesita, cuánto hay y cuánto falta, con `accion`: `comprar` o `producir`). Lo que falta de un insumo comprado **se suma a `comprar`** (el ítem dice para qué elaboración es en `para_elaborar`); si lo que falta es otra elaboración, se suman las tandas de esa otra, y así en cadena hasta la materia prima. Un insumo con falta por objetivo y por elaboración se pide por el mayor de los dos, no la suma.
4. **Orden de cocina:** `producir` va ordenado para cocinar primero lo que otras elaboraciones usan (la salsa base antes que la salsa picante); a igual nivel, por gravedad.
5. **Límites que quedan:** el cálculo no estima consumo futuro (no sabe cuánto se va a vender antes de que algo venza), y la lista no reserva el mismo ingrediente entre elaboraciones que no se dependen entre sí: para eso se suma el consumo de todas las que se planean, pero cada ítem informa `tandas_posibles` por separado.

- **Probarlo:** `python Tests\Scripts\probar_reposicion_calculos.py` (48 chequeos, no necesita nada corriendo), `python Tests\Scripts\probar_vencimientos.py` (ahora también prueba el aviso propio y la reposición contra la base) y la carpeta «10. Aviso por insumo y reposición (hito 6.1)» de la colección de Postman (requiere el script SQL 16).

## Cobros (hito 1): cotización oficial de las monedas

1. **Qué es:** la cuenta siempre está en pesos (ARS). La cotización de USD, BRL y PYG sirve para dos cosas: cobrar efectivo en esas monedas (el vuelto siempre es en pesos) y mostrar en la factura cuánto equivale el total en cada moneda, incluso si se paga con Mercado Pago. `valor` es **pesos por 1 unidad** de la moneda (`tipoCotizacion` del BCRA): `USD 1450` significa 1 USD = 1450 ARS. El guaraní vale ~0,24 pesos, por eso `Valor` tiene 8 decimales.
2. **Se actualiza sola, nadie la carga:** `python restaurante/worker_cotizacion.py` consulta la API de Estadísticas Cambiarias del BCRA cada 30 minutos (`COTIZACION_INTERVALO_SEG` en el `.env` lo cambia; `BCRA_URL` cambia la dirección). Guarda una fila nueva **solo si el valor cambió**, así `CotizacionMoneda` queda como historial. No existe ningún endpoint ni pantalla para escribir un valor: ni siquiera el Gerente o el Admin (`POST /cotizaciones/actualizar` solo vuelve a preguntarle al BCRA).
3. **Fines de semana y feriados:** el BCRA no publica esos días, así que se retrocede hasta 8 días buscando la última publicación y sigue vigente la última guardada. Lo mismo si no hay conexión: no se pierde nada, el worker reintenta a los 5 minutos y el estado muestra `desactualizada: true` si pasan más de 2 horas sin una consulta exitosa.
4. **Cada pago congela la suya:** más adelante (hito 3) cada pago en efectivo guarda la cotización que usó, y la factura guarda los equivalentes al emitirse; una cotización posterior no cambia lo ya cobrado.
5. **Cómo se pasa de una moneda a otra:** `restaurante/cobros_calculos.py` (sin base de datos ni red) hace las conversiones con `Decimal`, redondeo a centavos con la mitad hacia arriba, y reparte lo que entrega el cliente entre cuenta, propina y vuelto en pesos.
6. **Verificado contra el servicio real (6 nov 2026):** el BCRA respondió y se guardaron USD, BRL y PYG. Si la respuesta cambiara de forma, el lector lo registra como error en `ultimo_error` y mantiene la última cotización; lo mismo si falla el certificado TLS.

- **Probarlo:** `python Tests\Scripts\probar_cobros_calculos.py` (50 chequeos, no necesita nada corriendo) y la colección `Tests/Postman/Savage_Grill_Cobros.postman_collection.json` (requiere el script SQL 17, `runserver` y los usuarios del seed; si la PC no llega al BCRA, los chequeos que dependen del valor se saltean).

## Cobros (hito 2): caja

1. **Una sola caja abierta a la vez:** la abren y la cierran Admin y Gerente (`UQ_Caja_Abierta` lo garantiza en la base). Se puede abrir y cerrar con la jornada cerrada. El mozo solo consulta si está abierta (`GET /caja/actual`).
2. **Arqueo con dos medios:** *Efectivo* (el cajón, por moneda: ARS, USD, BRL y PYG) y *Mercado Pago* (dinero digital, siempre en pesos). El efectivo esperado es **apertura + ingresos − egresos** de cada moneda. Un cobro de Mercado Pago se anota en la caja **cuando el pago queda aprobado**, con la etiqueta `MercadoPago`; no pasa por el cajón, pero figura en el arqueo: lo esperado de Mercado Pago es la suma de esos cobros. Al cerrar se informa lo contado en el cajón (las cuatro monedas) y lo acreditado en la cuenta de Mercado Pago (`mercado_pago`, obligatorio si hubo cobros digitales), y se guarda la diferencia de cada medio (`informado − esperado`: negativo = faltante, positivo = sobrante). Una diferencia no impide cerrar: queda registrada y se avisa. Además se guarda el **total en pesos** (efectivo convertido con la cotización vigente + Mercado Pago), esperado e informado: cuánta plata hay juntando efectivo y dinero digital. Se compara lo bruto cobrado (la comisión de Mercado Pago se verá en el hito de Mercado Pago).
3. **Movimientos:** cada uno guarda su medio, su moneda, la cotización vigente en ese momento y su equivalente en pesos. Tipo `Ingreso` o `Egreso`; concepto `Manual` (lo carga Admin/Gerente con descripción obligatoria; siempre de efectivo) y, para los cobros del hito 3, `Venta`, `Propina` (la propina queda en la caja como **ingreso**: en efectivo en el cajón, con Mercado Pago en la cuenta digital), `Vuelto` (egreso en pesos) y `Anulacion`. Un egreso de efectivo no puede dejar el cajón en negativo en esa moneda.
4. **Sin carreras:** cada movimiento y el cierre bloquean la fila de la caja dentro de una transacción (`select_for_update`), así dos operaciones simultáneas no se pisan.
5. **Enchufado en el hito 3:** `bloqueos_de_cierre(caja)` impide cerrar la caja si hay un pago pendiente, y `registrar_movimiento(...)` es lo que usan los cobros en efectivo.

- **Probarlo:** `python Tests\Scripts\probar_caja_calculos.py` (74 chequeos, no necesita nada corriendo; `probar_caja_dobles.py` agrega 45 con modelos simulados) y la carpeta «2. Caja (hito 2)» de la colección `Savage_Grill_Cobros` (requiere el script SQL 18). La primera request de esa carpeta cierra la caja que haya abierta (con el arqueo exacto) para poder repetir la corrida.

## Cobros (hito 3): cuenta, pagos en efectivo y cierre de mesa

1. **Factura (cuenta interna, sin ARCA):** se emite cuando se empieza a cobrar y necesita la caja abierta y consumo. Congela el total, los renglones y cuánto equivale en USD, BRL y PYG con la cotización de ese momento. Hay **una vigente por sesión** (`UQ_Factura_Vigente`). La cuenta siempre está en pesos.
2. **Con la cuenta en curso la mesa no pide más:** la API responde `409` y el worker rechaza cualquier comanda que ya estuviera en la cola (bajo el bloqueo de la sesión, así una comanda y la factura de la misma mesa se ordenan). Para pedir algo más, el mozo cierra la sesión y abre otra; un Admin o Gerente también puede anular la factura si no tiene pagos.
3. **No se cobra con pedidos en preparación:** mientras una comanda esté `pendiente` o en `proceso` en cocina no se cobra. `listo` no bloquea; una comanda sin estado en Redis ya fue entregada.
4. **Pagos parciales y combinados:** `saldo = total − pagos aprobados − pagos pendientes`. Cuando lo aprobado cubre el total la factura queda `Pagada`; si se anula un pago, vuelve a `Emitida`.
5. **Efectivo:** un pago, una moneda (ARS, USD, BRL o PYG). Se convierte con la cotización vigente y esa cotización queda congelada en el pago. El **vuelto es siempre en pesos** y lo calcula el sistema (egreso `Vuelto` en la caja). La **propina** es opcional, en pesos, va **solo al mozo de la mesa** y queda en la caja como ingreso `Propina`.
6. **Sin doble cobro:** cada cobro bloquea la factura y la caja dentro de una transacción; reintentar con la misma `clave` devuelve el mismo pago.
7. **Anulaciones:** solo se anulan pagos en efectivo (Admin/Gerente, con motivo): el efectivo vuelve con un contramovimiento en la caja abierta. Cada cambio de un pago queda en `PagoEvento` (auditoría).
8. **Cierre de mesa:** sin consumo o con la factura pagada se cierra siempre. Con saldo: `409`, salvo que un Admin o Gerente fuerce con motivo (queda `CierreForzado`, `MotivoCierre` y quién lo hizo). Con un pago pendiente no se cierra nunca. Después de pagar, la mesa queda **en sobremesa** (sesión abierta con la factura `Pagada`; se deriva, no tiene columna propia) hasta que el mozo la libere cerrando la sesión.
9. **Plato compartido y comensales:** al enviar una comanda el cliente puede indicar `comensal` (su nombre) y, por plato, `compartido: ["Ana", "Beto"]`: ese plato se reparte en partes iguales entre los elegidos (los centavos sobrantes van a los primeros, la suma siempre da el total). `por_comensal` es solo informativo: lo que se cobra es el total de la factura.
10. **Importante, cambia respecto del hito 2:** una mesa con consumo ya no se cierra sin cobrar. Las colecciones de Postman que cierran mesas con pedidos usan el cierre forzado del Gerente.

- **Probarlo:** `python Tests\Scripts\probar_cuenta_calculos.py` (40 chequeos) y `python Tests\Scripts\probar_cuenta_dobles.py` (93 chequeos de las reglas de cuenta y de Mercado Pago con modelos simulados, sin base ni Django), más la carpeta «3. Cuenta y pagos (hito 3)» de la colección `Savage_Grill_Cobros` (requiere el script SQL 19, `runserver`, `worker.py`, RabbitMQ y Redis; usa la mesa 5 y deja la caja cerrada).

## Cobros (hito 4): Mercado Pago

1. **Checkout Pro con preferencias, iniciado por el cliente:** el cliente elige pagar con Mercado Pago desde su mesa (con el PIN), el sistema crea una *preferencia* (el link de pago) y lo redirige a Mercado Pago. No pasa por un QR del mozo. Se paga siempre en **pesos**.
2. **Qué se cobra:** la parte de la cuenta que el cliente elija (o todo el saldo) más una **propina** opcional, que va como ítem aparte y es del mozo de la mesa. Se puede pagar en partes y **combinar con efectivo**. Mientras el pago está pendiente **reserva su monto** del saldo; hay **un solo pago pendiente por factura** (tocar «pagar» de nuevo devuelve el mismo link).
3. **Antes de emitir la factura se valida todo:** un clic por error o con pedidos en cocina no congela la mesa (la factura recién se emite cuando el pago es posible).
4. **Confirmación por consulta periódica (por ahora):** el `worker_mercadopago.py` consulta a Mercado Pago cada 15 segundos por la referencia `SG-<id del pago>`, y el cliente o el mozo pueden pedir la confirmación al instante. El webhook se suma cuando el sistema tenga una URL pública con HTTPS (Azure); la consulta periódica queda como respaldo.
5. **Un rechazo no termina el cobro:** el cliente puede reintentar con el mismo link. El pago termina cuando se **aprueba**, cuando **vence el link** (`Expirado`, con unos minutos de margen y solo si no hay un pago en proceso) o cuando se **cancela** (`Cancelado`). Cancelar y vencer solo se hacen si Mercado Pago confirma que no se pagó; si no responde, el pago queda pendiente (por seguridad).
6. **Al aprobarse:** el pago pasa a `Aprobado` y la caja anota un ingreso `Venta` y otro `Propina` con el medio **MercadoPago** (sin cajero: lo registra el sistema). El arqueo los muestra aparte del efectivo y, al cerrar la caja, se declara cuánto se acreditó en la cuenta de Mercado Pago. Se registra el monto **bruto**; el neto (después de la comisión) queda como dato informativo.
7. **Controles:** si Mercado Pago informa un monto distinto al esperado, el pago **no se aprueba solo** (queda anotado en el historial para revisarlo). Un pago de Mercado Pago no se registra dos veces (`UQ_Pago_MpPagoId`). Una aprobación tardía (el link ya estaba vencido o cancelado pero el cliente pagó) igual se registra durante 3 horas, con el evento «Aprobacion tardia». Mientras haya un pago pendiente no se cierra la mesa ni la caja, ni se anula la factura. Los pagos de Mercado Pago no se anulan desde el sistema (la devolución se hace en Mercado Pago).
8. **Tres modos (`MP_MODO`):** `simulado` (por defecto; sin internet ni credenciales: el cobro lo «paga» un Admin o Gerente con `POST /pagos/{id}/simular`), `prueba` (Mercado Pago real con el *Access Token* de prueba) y `produccion`. Con `prueba` o `produccion` hace falta `MP_ACCESS_TOKEN` en el `.env`. En `prueba` se usa el *Access Token de prueba* de la aplicación (Mercado Pago Developers → Credenciales → entorno de prueba) y el mismo link `init_point`; para pagar en el checkout de prueba se usan las tarjetas de prueba de Mercado Pago, donde el resultado lo decide el nombre del titular (`APRO` aprobado, `OTHE` rechazado, `CONT` pendiente). En la VM el token se carga a mano en el `.env` y se reinician `api` y `worker_mercadopago`.

- **Probarlo:** `python Tests\Scripts\probar_cuenta_dobles.py` (incluye la lógica de Mercado Pago con una pasarela simulada: parcial con propina, combinación con efectivo, rechazo, en proceso, monto distinto, aprobación, vencimiento, aprobación tardía, cancelación, caída de Mercado Pago, caja cerrada) y la carpeta «4. Mercado Pago (hito 4)» de la colección `Savage_Grill_Cobros` (requiere el script SQL 20, `MP_MODO=simulado`, `runserver`, `worker.py`, RabbitMQ y Redis; usa la mesa 5 y deja la caja cerrada). El vencimiento del link (mínimo 5 minutos) solo se prueba con los dobles.

## Cobros (hito 5): extras por receta

1. **Qué es un extra:** algo que el cliente le **suma** a un plato y se cobra aparte («más cheddar», «aderezo»). Lo define Admin o Gerente **en la receta** (`POST /recetas/{id}/extras`), así que todos los platos que usan esa receta lo ofrecen. Cada extra dice qué insumo gasta, **cuánto gasta una unidad de extra**, **cuánto se cobra** por unidad y cuántas unidades admite cada plato (de 1 a 10).
2. **Cómo se pide:** cada item del pedido admite `"extras": [{"id": 4, "cantidad": 2}]`, por ejemplo `{"id": 12, "extras": [{"id": 4, "cantidad": 1}]}`. Sin `extras` el item es igual que antes. Se combina con `"sin"` (ver «Stock (hito 5)»), salvo con el **mismo** insumo: pedir «sin cheddar» y «extra de cheddar» a la vez es un error.
3. **Precio:** el precio del renglón es el del plato **más** el recargo de cada extra por su cantidad. Como el plato, **cada extra se cobra al precio que el cliente vio** en su menú (`version_menu`): si subió mientras armaba el pedido paga el que vio, y si bajó paga el nuevo. El recargo queda congelado en `PedidoDetalleExtra`, así que cambiar el precio después no toca lo ya vendido.
4. **Stock:** lo que gasta el extra **se suma a la receta del plato** (si la receta ya usa ese insumo, se suma a la misma línea) y se descuenta por FEFO junto con el resto, en la misma transacción. Dos renglones del mismo plato con distintos extras son renglones distintos.
5. **Qué se ofrece:** el menú (`GET /productos`) trae en cada plato `extras: [{id, nombre, precio, max_por_unidad}]`, solo los **activos y con stock** para al menos una unidad; no muestra cantidades ni datos internos. Cuando el stock de un extra no alcanza, deja de ofrecerse solo y vuelve cuando se repone; desactivarlo a mano (`activo: false`) lo saca de la carta sin borrar el historial.
6. **Validación (`409 extras_invalidos`):** el pedido se rechaza entero, con `extras_invalidos: [{id, producto, extra, nombre, motivo}]`, si algún extra tiene un `motivo` de estos: `no_existe`, `no_pertenece` (es de otra receta), `fuera_de_carta` (desactivado), `sin_stock`, `excede_maximo` o `incompatible_con_sin`. Si los extras son válidos pero el stock total no alcanza, responde `409 productos_sin_stock`, igual que sin extras.
7. **Si el extra se agota justo al confirmar:** el worker rechaza la **comanda entera** (decisión de producto: no se sirve el plato sin el extra que el cliente pagó). Queda en `comandas-rechazadas` con el motivo interno.
8. **Dónde se ve:** el tablero de Cocina (`extras`: lista de textos, `["Cheddar", "Aderezo x2"]`), el historial de la mesa (`extras: [{nombre, cantidad, precio}]`, donde `precio` ya está incluido en el del renglón), el ticket PDF y la factura («Hamburguesa (sin cebolla; con Cheddar x2)»).
9. **Copiar extras entre recetas:** `POST /recetas/{id}/extras/copiar {"origen": 3}` evita cargar los mismos extras en cada receta. No pisa los que la receta ya tiene; el precio de la copia es independiente del original.
10. **Borrado:** un extra usado en algún pedido no se borra (`409`); se desactiva. Una receta con extras usados tampoco se borra, para no perder el historial.
11. **Por qué una tabla aparte (`PedidoDetalleExtra`):** los extras son una lista por renglón, igual que los ingredientes quitados; guardarlos como texto rompería la primera forma normal y no permitiría sumar el consumo de cada insumo ni auditar el recargo cobrado.

- **Probarlo:** `python Tests\Scripts\probar_extras_calculos.py` (39 chequeos: clave de línea, receta con extras, alcance del stock, precio y las seis validaciones) y la carpeta «5. Extras por receta (hito 5)» de la colección `Savage_Grill_Cobros` (requiere el script SQL 21, `runserver`, `worker.py`, RabbitMQ y Redis; usa la mesa 5, crea sus propios insumos, recetas y proveedor con un sufijo aleatorio y al terminar desactiva lo que creó). El caso «el extra se agota justo al confirmar» depende de una carrera entre dos pedidos y no se prueba en Postman.

## Cobros (hito 6): comprobante PDF y auditoría

1. **La factura interna siempre existe; el PDF es opcional.** Hace falta una factura para cobrar (congela el total y los renglones), pero el comprobante PDF solo se genera si el cliente lo quiere. Antes de pagar se le muestra una casilla «¿Quiere factura?» y, si la tilda, escribe el nombre de quien paga. Es un comprobante interno: no reemplaza a la factura fiscal de ARCA y lo dice en el pie.
2. **Dónde viaja la casilla:** en el cuerpo de los endpoints de pago, `"quiere_factura": true, "nombre_factura": "David"`, tanto en `POST /cuenta/pagar/mercadopago` (el cliente, antes de ir a Mercado Pago) como en `POST /facturas/{id}/pagos/efectivo` (el mozo, en el salón). Tildada, el nombre es obligatorio (`400`). Si el cuerpo no trae la casilla, no cambia lo ya elegido; destildada, el nombre se borra. **Se valida antes de cobrar** (un error de la casilla no deja un cobro hecho ni un link creado) y **se guarda después**. Mientras la factura siga vigente se puede corregir con `POST /cuenta/factura` (cliente) o `PATCH /facturas/{id}/comprobante` (personal).
3. **Un solo comprobante por mesa:** reúne los renglones, cada pago (medio, moneda, lo recibido con su cotización, propina y vuelto), el total de la cuenta, la propina, lo cobrado y lo que equivale el total en USD, BRL y PYG con las cotizaciones congeladas al emitir la factura. Marca de Savage Grill (negro y naranja), con paginación automática si el consumo es largo.
4. **Cuándo se baja:** solo si se pidió la factura y está `Pagada`. Si después se anula un pago en efectivo, la factura vuelve a `Emitida` y el comprobante deja de estar disponible hasta que se complete el cobro. El JSON de la cuenta trae `factura.quiere_factura`, `factura.nombre_factura` y `factura.comprobante_disponible` para que el front muestre u oculte el botón.
5. **Nombre del archivo:** `Nombre - dd-mm-aa.pdf` (por ejemplo `David - 08-11-26.pdf`), con la fecha del pago, en el encabezado `Content-Disposition`. La barra no se puede usar en un nombre de archivo, por eso la fecha lleva guiones. Se usa el nombre que se escribió en la casilla (el de la cuenta de Mercado Pago no se consulta).
6. **Dónde queda el archivo:** al quedar `Pagada` una factura que se pidió, el PDF se **guarda en la carpeta `Facturas/`** (en la raíz del proyecto, junto a `tickets/`; no se versiona) como `David - 08-11-26 (factura 7).pdf`; el número de factura evita que dos clientes con el mismo nombre se pisen. Si la factura deja de estar `Pagada` (se anuló un pago) o se destilda la casilla, el archivo se borra. Guardarlo nunca puede hacer fallar un cobro: si no se puede, queda en el log. La descarga por la API genera el PDF en el momento (todo lo que muestra está congelado en la base, así que sale igual) y su nombre no lleva el número de factura. El PIN del cliente va en el cuerpo de un `POST`, no en la URL, para que no quede en registros ni en el historial del navegador: el front lo pide con `fetch` y guarda el resultado como archivo.
7. **Tickets de comanda y facturas son cosas distintas:** el *ticket* es el comprobante de **cada pedido** a cocina (lo genera `worker_pdf.py` cuando Cocina marca la comanda como `listo`) y va en `tickets/`; la *factura* es **una por mesa**, con la cuenta completa y sus pagos, y va en `Facturas/`. Los tickets ahora se llaman **`MESA 2 - Pedido 1 (<uuid>).pdf`**: el «Pedido N» cuenta las comandas aceptadas de esa sesión de la mesa, en orden, y el UUID se conserva porque es la clave con la que el front lo pide (`/tickets/<uuid>.pdf` y `/pedidos/<uuid>/ticket` no cambian). Quien lo baja ve el nombre sin el UUID (`MESA 2 - Pedido 1.pdf`) y los tickets viejos, llamados solo por el UUID, se siguen encontrando. Esa búsqueda vive en `views_tickets.py` (no en `views.py`, para no pisar el trabajo del front).
8. **Auditoría = línea de tiempo de solo lectura**, sin tablas nuevas: reúne lo que el cobro ya registra (`PagoEvento`, `MovimientoCaja`, `Caja`, `Factura` y los cierres de mesa forzados) en una sola lista ordenada. Cada evento trae `fecha_hora`, `tipo`, `evento`, una `descripcion` lista para mostrar (por ejemplo «Pago #11 (Efectivo): Anulado (Aprobado -> Anulado). Error de carga»), quién lo hizo (`empleado: {id, nombre}`, o `null` si lo registró el sistema, como las aprobaciones de Mercado Pago), la mesa, la factura, el pago, la caja, el monto y la moneda. Un filtro que no corresponde a un tipo lo deja afuera (con `caja` salen solo movimientos y aperturas/cierres de esa caja, porque un pago o una factura no pertenecen a una caja). Cada fuente trae solo lo más nuevo que hace falta para la página pedida, así que se puede consultar con un historial largo.

- **Probarlo:** `python Tests\Scripts\probar_comprobante_calculos.py` (112 chequeos: importes en formato argentino, nombre del archivo, validación de la casilla, contenido del comprobante y dibujo con un doble estricto de la librería de PDF) y `python Tests\Scripts\probar_auditoria_calculos.py` (48 chequeos: filtros, una frase por tipo de evento, mezcla y paginación), `python Tests\\Scripts\\probar_comprobante_dobles.py` (la copia en `tickets/`: se guarda, se reemplaza, se borra y no pisa otras facturas), ninguno necesita nada corriendo; y la carpeta «6. Comprobante y auditoría (hito 6)» de la colección `Savage_Grill_Cobros` (requiere el script SQL 22, `MP_MODO=simulado`, `runserver`, `worker.py`, RabbitMQ y Redis; usa la mesa 5 y al terminar deja la caja cerrada con el arqueo exacto). Lo que los scripts no pueden probar es el dibujo real con `fpdf2`: se ve abriendo el PDF que baja Postman.

## Reservas

Las cargan **Admin y Gerente** a partir de llamadas y mensajes (el mozo solo las consulta). No hay autogestión ni seña: queda como siguiente etapa.

- **Una reserva es de una jornada** (fecha + turno: Almuerzo, Cena...) y **no tiene duración**: bloquea la mesa **toda la jornada**. Hay una sola reserva `Confirmada` por mesa y jornada (la base lo garantiza con un índice único); para la misma mesa se elige otro turno u otra fecha.
- **Estados:** `Confirmada` → `Cumplida` (el cliente llegó y se abrió la mesa por su reserva), `Cancelada` (el cliente avisó que no viene) o `No se presentó` (no llegó dentro de la tolerancia).
- **Abrir una mesa reservada:** `POST /sesiones-mesa/abrir` responde **409** con `codigo: "mesa_reservada"` y los datos de la reserva (nombre, apellido, hora, turno). El mozo confirma que es la del cliente y vuelve a enviar con `reserva_id`; la reserva pasa a `Cumplida` y queda ligada a la sesión. **Nadie** abre una mesa reservada para otra persona, tampoco Admin ni Gerente: si el cliente avisa que no viene, se cancela la reserva.
- **Tolerancia:** 30 minutos después de la hora de llegada (`RESERVA_TOLERANCIA_MINUTOS` en el `.env`, por defecto 30). Pasado ese tiempo, la reserva pasa **sola** a `No se presentó` y la mesa queda libre. No hay un proceso aparte: se aplica al abrir una mesa y al consultar mesas y reservas.
- **Mapa de mesas:** `GET /mesas` suma `reserva` (id, nombre, apellido, hora, turno, personas) en la mesa que la jornada abierta tiene reservada, y `null` en las demás.
- **Se puede reservar una mesa en particular** (`numero_mesa`) o dejar que el sistema elija la más chica libre que alcance. Se valida capacidad, que la hora esté dentro del turno, que no sea en el pasado y que la mesa no esté ocupada en la jornada en curso.

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /reservas` | Mozo, Admin, Gerente | Lista. Filtros: `fecha`, `desde`, `hasta` (sin fechas: desde hoy), `turno`, `mesa`, `estado` |
| `POST /reservas` | Admin, Gerente | Alta: `nombre`, `apellido`, `telefono`, `fecha`, `turno` (id), `hora` (HH:MM), `cantidad_personas`; opcionales `numero_mesa`, `notas`, `origen` |
| `GET /reservas/{id}` | Mozo, Admin, Gerente | Detalle |
| `PATCH /reservas/{id}` | Admin, Gerente | Edita una reserva `Confirmada` (se manda solo lo que cambia) |
| `POST /reservas/{id}/cancelar` | Admin, Gerente | Cancela (cuerpo opcional `{"motivo": "..."}`). No se borran: quedan en el historial |
| `GET /reservas/disponibilidad?fecha=&turno=&personas=` | Mozo, Admin, Gerente | Mesas libres para esa jornada y la sugerida |

- **Probarlo:** `python Tests\Scripts\probar_reservas_calculos.py` (47 chequeos: horarios de los turnos, turno que cruza la medianoche, tolerancia, teléfono, elección de mesa y mensajes; no necesita nada corriendo) y la colección `Savage_Grill_Reservas` de Postman (requiere el script SQL 23 y `runserver`; cubre alta, validaciones, disponibilidad, edición, cancelación y apertura de mesa por la reserva). El vencimiento automático depende del reloj y lo cubre el script de cálculos.

## Cobros (hito 7): pago con tarjeta

Manual y tercerizado: no hay pasarela ni API. El cliente pide pagar con tarjeta de crédito o débito, el mozo recibe el aviso, le lleva el postnet y, **cuando la plata impactó, confirma el cobro en el sistema**.

- **Aviso al mozo:** `POST /solicitar-cuenta` acepta `metodo_pago` (`efectivo`, `tarjeta` o `mercadopago`). Es solo un aviso: se guarda en la sesión y `GET /mesas` lo devuelve como `metodo_pago_solicitado` (junto con `solicita_cuenta`), para mostrarlo en «Avisos del salón». Se puede cambiar volviendo a pedir la cuenta. Un valor que el sistema no maneja (por ejemplo `transferencia`) se ignora y no hace fallar la solicitud.
- **Confirmar el cobro:** `POST /facturas/{id}/pagos/tarjeta` (Mozo en sus mesas, Admin, Gerente). Cuerpo opcional: `monto_cuenta` (pesos; sin indicar, todo el saldo), `clave` (reintento sin cobrar dos veces) y `quiere_factura` / `nombre_factura`, igual que en efectivo. Responde `{pago, cuenta}` con el mismo formato que el cobro en efectivo (`pago.metodo` = `Tarjeta`).
- **Reglas:** el pago nace `Aprobado`, en pesos, sin vuelto ni propina. Se puede pagar en partes y combinar con efectivo o Mercado Pago. Como todo cobro, pide caja abierta y que no haya pedidos en preparación (409). No pasa por el arqueo de la caja: **no genera movimientos de efectivo**, y el cierre de la terminal del postnet queda fuera del sistema.
- **Corregir un error:** un Admin o Gerente anula un cobro con tarjeta confirmado por error con `POST /pagos/{id}/anular` (con motivo); la cuenta se reabre.
- **Probarlo:** `python Tests\Scripts\probar_tarjeta_calculos.py` (25 chequeos: medio solicitado y monto del cobro; no necesita nada corriendo) y la colección `Savage_Grill_Tarjeta` de Postman (requiere los scripts SQL 19 y 24, `runserver`, `worker.py`, RabbitMQ y Redis; usa la mesa 5 y al terminar deja la caja cerrada).

## Comensales y seguridad de la mesa

**Modalidad.** El mozo la elige al abrir la mesa (`POST /sesiones-mesa/abrir`, campo opcional `modalidad`: `Familiar` por defecto o `Grupal`). `GET /mesas` y `POST /acceso-mesa` devuelven `modalidad` y `ronda_liberada`.
- **Familiar:** todos los dispositivos agregan al pedido con el mismo PIN, sin esperar a nadie; el nombre es opcional y la cuenta va a nombre de una persona (se carga al cobrar, `nombre_factura`).
- **Grupal:** cada dispositivo se presenta con su nombre y todo pedido es de un comensal. **Cada uno pide cuando quiere: su pedido sale a cocina enseguida, sin esperar el OK de los demás** (la mesa nace con `ronda_liberada: true`). La espera del OK en la primera ronda (comandas `retenida` hasta que todos confirman o el mozo libera) sigue implementada pero **desactivada**: se reactiva poniendo `PRIMERA_RONDA_CON_OK = True` en `restaurante/comensales_calculos.py`. Mientras está desactivada, `POST /mesa/comensales/ok` y `POST /sesiones-mesa/{id}/liberar-ronda` no cambian nada (`liberada_ahora: false` y `liberadas: 0`) y el front no necesita mostrar el botón de OK.

**Cliente** (sin login, con `numero_mesa` y `pin` en el cuerpo):
- `POST /mesa/comensales` `{numero_mesa, pin, nombre}` → registra al dispositivo. Mismo nombre en la misma mesa (sin distinguir mayúsculas ni acentos) = misma persona: `situacion` = `nuevo`, `existente` o `reactivado` (se había retirado y volvió con el PIN nuevo). Devuelve `comensal.id`, que el front manda en `id_comensal` al pedir (`POST /pedidos`). En una mesa Grupal es obligatorio: sin él responde 409 `comensal_requerido`.
- `POST /mesa/comensales/estado` → modalidad, comensales (`estado` Activo/Retirado y `ok`), `espera_ok` y `faltan_por_ok`. Es el que se consulta cada pocos segundos.
- `POST /mesa/comensales/ok` `{..., id_comensal, ok}` → «ya pedí todo» (también vale «nada más por ahora»); `ok: false` lo retira para seguir pidiendo. Si con eso todos dieron el OK, `liberada_ahora: true` y la primera ronda sale junta a cocina. Pedir algo antes de que salga la ronda reinicia el OK de quien pidió.
- `POST /mesa/regenerar-pin` `{numero_mesa, pin, id_comensal, retirados: [ids]}` → cualquier comensal pide un PIN nuevo. **La mesa sigue siendo la misma sesión**: lo ya pedido y comido queda en la cuenta. Quien pide marca de la lista quiénes se fueron; de cada uno se **cancelan los pedidos que todavía no se empezaron a preparar** (`retenida` o `pendiente`) con devolución de stock, y lo que está en proceso o más adelante queda en la cuenta. Sin retirados no se cancela nada. El PIN nuevo **no se devuelve al cliente**: el mozo recibe un aviso urgente (`aviso_pin` en `GET /mesas`) y se lo da a los que se quedan. Entre dos pedidos hay 30 segundos de espera (429 `espera_pin`).
- Un dispositivo con el PIN viejo recibe 403 con `codigo: "pin_cambiado"` y **no se cuenta como intento fallido**, así no bloquea por IP a quienes ya entraron con el PIN nuevo. Un comensal retirado que intenta pedir recibe 403 `comensal_retirado`.

**Personal** (Mozo en sus mesas, Admin y Gerente):
- `GET /sesiones-mesa/{id}/comensales` → mismo resumen que el estado del cliente.
- `POST /sesiones-mesa/{id}/liberar-ronda` → libera la primera ronda sin esperar el OK de todos (solo mesas Grupales). Devuelve `liberadas`.
- `POST /sesiones-mesa/{id}/regenerar-pin` `{retirados: [ids]}` → el mozo cambia el PIN (sin espera entre cambios) y recibe el PIN nuevo en `pin`.
- `POST /sesiones-mesa/{id}/pin/visto` → confirma el aviso de PIN nuevo. El PIN vigente se lee en `GET /sesiones-mesa/{id}`.
- `POST /pedidos/{uuid}/cancelar` `{motivo}` → cancela una comanda `retenida` o `pendiente`: devuelve el stock (movimientos `Devolucion` en el libro) y la saca de la cuenta; queda como `cancelada` en el historial. Una comanda en proceso, lista o entregada responde 409 `no_cancelable`.

**Cierre y cobro.** Con pedidos sin entregar (`retenida`, `pendiente`, `proceso` o `listo`) la mesa no se cierra (409 `comandas_pendientes`, con la lista). Un Admin o Gerente puede forzar el cierre con `forzar` y `motivo`: lo que no empezó a prepararse se cancela con devolución de stock y lo demás se da por entregado. Si la mesa ya se pagó, el mozo la cierra a mano cuando quiera (sobremesa). Una comanda `retenida` también impide cobrar. En el historial del cliente cada comanda trae el `comensal` que la pidió.

**Probarlo:** `python Tests\Scripts\probar_comensales_calculos.py` (52 chequeos) y `python Tests\Scripts\probar_estado_comandas.py` (14, con un Redis de mentira); no necesitan nada corriendo. Y la colección `Savage_Grill_Comensales` de Postman (requiere el script SQL 25, `runserver`, `worker.py`, RabbitMQ y Redis; usa las mesas 6 a 9 y las deja cerradas).

## Barra, bartender y bebidas del mozo

Cada producto se prepara o se entrega en un **destino**:

| Destino | Qué es | Quién lo ve |
|---|---|---|
| `COCINA` | Entradas, principales, postres… (lo de siempre) | Tablero de cocina |
| `BARRA` | Los tragos: los prepara el bartender | Tablero de la barra |
| `MOZO` | Las bebidas: no se preparan, solo se llevan a la mesa | Aviso «Bebidas» del mozo de esa mesa |

- **Cómo se decide.** Por la categoría del producto: *Tragos* → `BARRA`, *Bebidas* → `MOZO`, el resto → `COCINA`. Un producto puede tener su propio destino (`destino` en `POST/PATCH /productos`: `COCINA`, `BARRA`, `MOZO` o `null` para volver al de la categoría) y ese gana. `GET /productos` informa `destino` (el propio, o `null`) y `destino_efectivo` (el que rige hoy). El destino de cada ítem se guarda al pedirse (`PedidoDetalle.Destino`): editar el producto después no mueve los pedidos ya hechos.
- **Una comanda se divide por destino.** Un pedido con plato, trago y bebida es una sola comanda (un solo UUID, una sola cuenta, un solo stock) pero tiene **un estado por destino** en Redis (`comanda:estado:<uuid>` para cocina, `…:barra`, `…:mozo`). Cada sector avanza por su cuenta y cada tablero muestra **solo sus ítems**. Para el cliente y para el cierre de mesa, la comanda está «tan avanzada como su sector más atrasado»; está entregada cuando ya no queda ningún sector pendiente.
- **Bartender.** Rol nuevo (`Bartender`; usuario de demostración `tbarrios`, clave `1234`). `GET /barra/tablero` tiene el mismo formato que el de cocina y `PATCH /barra/pedidos/{uuid}/estado` `{estado}` avanza `pendiente → proceso → listo → entregado`. Cocina no mueve los tragos ni el bartender los platos (403).
- **Bebidas del mozo.** Nacen listas para llevar (`listo`). `GET /mozo/bebidas` devuelve las de **sus** mesas (un Admin o Gerente ve todas): `id_comanda_uuid`, `numero_mesa`, `mesa_id`, `id_sesion`, `comensal`, `items` (`nombre`, `cantidad`) y `timestamp`. La única acción del mozo es `POST /pedidos/{uuid}/bebidas/entregar` (**Entregado**); un mozo no puede confirmar las de una mesa ajena (404). Se consulta cada pocos segundos: lo entregado desaparece solo.
- **Mesa grupal.** Cada comensal pide cuando quiere: cocina y barra reciben su parte como `pendiente` y las bebidas quedan `listo` para el mozo enseguida. (Si se reactiva la espera del OK, la primera ronda nace `retenida` en los tres sectores hasta que todos confirman o el mozo la libera.)
- **Cancelar.** `POST /pedidos/{uuid}/cancelar` cancela la comanda entera mientras **ni cocina ni barra empezaron** (`retenida` o `pendiente`) y las bebidas no se llevaron al servirse; en cuanto un sector empieza, responde 409 `no_cancelable`. Las bebidas listas del mozo no impiden cancelar.
- **Stock.** Sin cambios: el stock de todos los ítems (platos, tragos y bebidas con receta) se descuenta al aceptar la comanda y se devuelve al cancelarla, sin importar el destino.
- **Seguridad.** Se cerraron las rutas que estaban públicas: el tablero de cocina solo lo leen Cocina, Mozo, Admin y Gerente, y mover una comanda exige Cocina, Admin o Gerente (la barra, Bartender, Admin o Gerente). Los pedidos sin token responden 401.

**Probarlo:** `python Tests\Scripts\probar_destinos_calculos.py` (41 chequeos), `python Tests\Scripts\probar_estado_comandas.py` (34, con un Redis de mentira) y la colección `Tests/Postman/Savage_Grill_Barra.postman_collection.json` (87 pasos; con `runserver`, `worker.py`, RabbitMQ y Redis activos, el script 26 aplicado y el seed 99 para el usuario `tbarrios`; la primera vez esperar un minuto tras reiniciar el servidor, porque el menú está cacheado 60 s).

## Carga de fotos de productos

Las fotos del menú se cargan de una vez desde un `.zip` (con las fotos en `media/productos/`) y un `.csv` sin encabezado, separado por `;`, con una fila por producto: `id;nombre;/media/productos/<32 hex>.jpg|png|webp`. El comando busca cada producto **por nombre** (sin importar mayúsculas ni acentos; el `id` del CSV puede no coincidir con el de la base), copia la foto a `media/productos/`, guarda su ruta en el producto y actualiza el menú de los clientes.

```powershell
python manage.py cargar_imagenes_productos fotos.zip imagenes.csv --simular   # solo muestra qué haría
python manage.py cargar_imagenes_productos fotos.zip imagenes.csv             # carga
python manage.py cargar_imagenes_productos fotos.zip imagenes.csv --pisar     # también reemplaza las fotos ya cargadas
```

- **Se puede repetir:** un producto que ya tiene foto no se toca (salvo `--pisar`), así que correrlo dos veces no duplica nada. Al final informa qué productos del CSV no existen en la base, cuáles tienen nombre repetido (no se adivina) y cuáles siguen sin foto.
- **Seguridad:** solo se aceptan archivos `media/productos/<32 hex>.jpg|png|webp` dentro del zip (nada de rutas con `..`), de hasta 2 MB y cuyo contenido sea realmente esa imagen.
- **En la VM:** la base y la carpeta de fotos de la VM son propias, por eso se corre ahí también: `docker compose -f docker-compose.prod.yml cp fotos.zip api:/tmp/` y `cp imagenes.csv api:/tmp/`, y luego `docker compose -f docker-compose.prod.yml exec api python manage.py cargar_imagenes_productos /tmp/fotos.zip /tmp/imagenes.csv`. Las fotos quedan en el volumen `media`, que es el que sirve Caddy.
- **Probarlo:** `python Tests\Scripts\probar_imagenes_carga.py` (22 chequeos de las reglas, sin Django ni base).

## Reinicio de la demo y stock realista

Scripts de mantenimiento en `sql/mantenimiento/`. **No son parte de la instalación** (el deploy solo corre los `NN_*.sql` de `sql/`): se ejecutan a mano en SSMS.

**Camino recomendado: `rehacer_demo_completa.sql`.** Deja la base lista para la demo en un solo paso, todo o nada:

- **Borra:** pedidos, comandas, comensales, facturas, pagos, cajas; todos los productos, recetas, insumos, lotes, compras, proveedores, pérdidas, producciones y especiales (incluida la basura de prueba `ZZ`). Las mesas quedan libres.
- **Conserva:** empleados, roles, mesas, categorías, turnos, jornadas, cotizaciones, configuración y reservas (se les suelta el vínculo con la sesión de mesa; con `@BorrarReservas = 1` también se borran).
- **Crea:** los 35 productos de la carta (sin fotos: se cargan después con `cargar_imagenes_productos`), una receta por producto con gramajes por porción, ingredientes quitables y extras con su recargo, 3 proveedores (Frigorífico Del Litoral, Verdulería Mayorista Posadas, Distribuidora Almacén y Bebidas) vinculados a los insumos según su nombre, y un stock realista: lo que gasta una porción por 40 porciones (perecederos) o 60 (larga vida), que además queda como `StockObjetivo` del semáforo. Los perecederos entran en dos lotes (60 % y 40 %) con vencimientos distintos.
- Si la carta no queda completa (un producto sin receta) o algo falla, **deshace todo** y lo informa.

Cómo usarlo:

1. **Copia de seguridad** en SSMS: clic derecho en `RestauranteDB` → *Tasks* → *Back Up…* → *OK*. Para volver atrás: *Restore Database*. Es **irreversible** sin la copia.
2. Abrir el script y ejecutarlo. Viene con `@Aplicar = 1` (aplica de verdad); con `@Aplicar = 0` hace todo, muestra el informe y lo deshace (ensayo).
3. Esperar 1 minuto (el menú se guarda en caché 60 s) o reiniciar `runserver`.

Después de correr las colecciones de Postman, que vuelven a crear datos de prueba y consumen stock, repetir el script para volver al estado de la demo.

## Estructura del repositorio

```
├── config/            configuración de Django (settings, urls)
├── restaurante/       API: modelos, vistas, serializers, auth, workers (RabbitMQ)
├── sql/               scripts de base de datos (creación, migraciones, seed)
├── frontend/          páginas HTML, app.js, styles.css y fonts (Gonzalo)
├── legacy/            servidor de ejemplo de AE1 (SERV_WEB.py), fuera del sistema actual
├── tickets/           tickets de comanda en PDF (no se versiona)
├── Facturas/          facturas en PDF de las mesas pagadas que las pidieron (no se versiona)
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
- Script de datos semilla (`sql/99_Seed_AE4.sql`, reemplaza al de AE2), idempotente.

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
