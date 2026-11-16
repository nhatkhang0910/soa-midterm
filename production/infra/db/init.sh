#!/bin/sh
set -eu
for name in auth wallet tuition payment notification; do
    upper=$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')
    password=$(printenv "${upper}_DB_PASSWORD")
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -v name="$name" -v password="$password" <<'SQL'
CREATE ROLE :"name" LOGIN PASSWORD :'password';
CREATE DATABASE :"name" OWNER :"name";
REVOKE CONNECT ON DATABASE :"name" FROM PUBLIC;
SQL
done
