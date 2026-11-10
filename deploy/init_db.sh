#!/bin/bash
# Crea RestauranteDB y corre los scripts de sql/ en orden (00 -> 22 y despues el seed 99).
# Es idempotente: si ya existe la base y el esquema solo repite los scripts 01 a 22 y el seed, que se pueden correr varias veces.
# Corre dentro del contenedor "sql_init" (misma imagen que SQL Server, que ya trae sqlcmd).
set -euo pipefail

# Se busca con un bucle y no con "ls | head": ls devuelve error 2 si falta alguno de los dos y con pipefail eso cortaba el script.
SQLCMD=""
for candidato in /opt/mssql-tools18/bin/sqlcmd /opt/mssql-tools/bin/sqlcmd; do
    if [ -x "$candidato" ]; then SQLCMD="$candidato"; break; fi
done
[ -n "$SQLCMD" ] || { echo "No se encontro sqlcmd en la imagen"; exit 1; }
CONFIAR=""
case "$SQLCMD" in *tools18*) CONFIAR="-C" ;; esac   # tools18 exige confiar en el certificado autofirmado de SQL Server

# -b: sale con error si un script falla. -I: QUOTED_IDENTIFIER activado (los indices filtrados lo exigen, como en SSMS).
# -f 65001: los scripts estan en UTF-8 (hay tildes y enies).
sql() { "$SQLCMD" $CONFIAR -S sqlserver -U sa -P "$MSSQL_SA_PASSWORD" -b -I -f 65001 "$@"; }

echo "[init] Esperando a SQL Server..."
for i in $(seq 1 60); do
    sql -d master -Q "SELECT 1" >/dev/null 2>&1 && break
    sleep 2
    [ "$i" -lt 60 ] || { echo "[init] SQL Server no respondio"; exit 1; }
done

echo "[init] Base RestauranteDB..."
sql -d master -Q "IF DB_ID('RestauranteDB') IS NULL CREATE DATABASE RestauranteDB;"

HAY_ESQUEMA=$(sql -d RestauranteDB -h -1 -W -Q "SET NOCOUNT ON; SELECT CASE WHEN OBJECT_ID('dbo.Rol','U') IS NULL THEN 0 ELSE 1 END" | tr -d '[:space:]')
# El script 00 no es idempotente: solo se corre en una base vacia. Se le saca el BOM (si lo tuviera) para que sqlcmd no lo lea como texto.
correr() { sed '1s/^\xEF\xBB\xBF//' "$1" | sql -d RestauranteDB; }

if [ "$HAY_ESQUEMA" = "0" ]; then
    echo "[init] 00 (esquema base)"
    correr /sql/00_Creacion_RestauranteDB.sql
else
    echo "[init] 00 omitido: el esquema ya existe"
fi

for f in $(ls /sql/[0-9][0-9]_*.sql | sort); do
    n=$(basename "$f")
    case "$n" in 00_*|99_*) continue ;; esac
    echo "[init] $n"
    correr "$f"
done

echo "[init] 99_Seed_AE4.sql"
correr /sql/99_Seed_AE4.sql
echo "[init] Listo."
