# Imagen de la API de Savage Grill (Django + gunicorn) y de sus workers: la misma imagen, distinto comando.
# bookworm = Debian 12, la version para la que Microsoft publica el driver ODBC 18 de SQL Server.
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Driver ODBC 18 de Microsoft (lo usa mssql-django a traves de pyodbc) y lo minimo para compilar si hiciera falta.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates gcc g++ unixodbc-dev \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
 && apt-get purge -y --auto-remove gnupg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Usuario sin privilegios. Las carpetas que se escriben en tiempo de ejecucion (fotos, tickets de comanda y facturas PDF)
# se crean aca para que los volumenes de Docker nazcan con su dueno.
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /app/media /app/tickets /app/Facturas \
 && chown -R app:app /app
COPY --chown=app:app config ./config
COPY --chown=app:app restaurante ./restaurante
COPY --chown=app:app manage.py ./
USER app

EXPOSE 8000
# 1 proceso con muchos hilos: el aviso en tiempo real del menu (SSE) deja una conexion abierta por cliente.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "120", "--timeout", "120", "--access-logfile", "-"]
