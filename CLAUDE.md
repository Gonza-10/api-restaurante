
# Savage Grill — API REST (Django REST Framework + SQL Server)

Proyecto académico UCP (Paradigmas III y Base de Datos). Todo en español: código, comentarios, mensajes de error y documentación.

## Estructura

`config/` y `restaurante/` (Django) · `sql/` (scripts de base de datos) · `frontend/` (HTML/JS/CSS, de Gonzalo) · `legacy/` (SERV_WEB.py de AE1) · `tickets/` y `media/` (generados, no se versionan).

## Reglas del esquema

- Todos los modelos son `managed = False`. La fuente de verdad del esquema son los scripts de `sql/`; `models.py` los refleja.
- Nunca correr `makemigrations`/`migrate` esperando crear tablas del negocio. Cambios de esquema: primero el script SQL, después `models.py`.
- No ejecutar SQL destructivo (DROP, DELETE masivo) sin pedir confirmación.

## Cómo correr

Requiere SQL Server (RestauranteDB), RabbitMQ (5672) y Redis (6379) activos. En PowerShell, con el venv activo:

- `python manage.py runserver 8080`
- `python restaurante/worker.py` (comandas)
- `python restaurante/worker_pdf.py` (tickets PDF)

## Git

- Se trabaja en `feature/back-api`, que parte de `arreglos`. `arreglos` integra back y front; `main` solo versiones completas. Nunca commitear directo a `main`.
- Commits semánticos (feat, fix, chore, docs...).
- El front (*.html, app.js, styles.css) lo desarrolla Gonzalo: no modificarlo salvo pedido explícito.

## Seguridad

- No leer ni commitear `.env`. Contraseñas siempre hasheadas.
- Rutas sin barra final (`/api/v1/productos`).
- Permisos por rol: cada vista declara `roles_lectura` / `roles_escritura` (ver `restaurante/auth.py`); `None` = público y si falta, se exige Admin o Gerente. Toda vista nueva debe declararlos.
- La `SECRET_KEY` sale del `.env` y firma los tokens de login: nunca hardcodearla.
