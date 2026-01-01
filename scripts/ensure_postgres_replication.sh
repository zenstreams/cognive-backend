#!/usr/bin/env bash
set -euo pipefail

# Ensures Postgres primary is configured for streaming replication:
# - creates/updates the `replicator` role with POSTGRES_REPL_PASSWORD
# - adds pg_hba.conf entries for replication from docker network
# - reloads Postgres config
#
# This is intentionally safe to run multiple times.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

ENV_FILE="${ROOT_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: .env not found at ${ROOT_DIR}/.env"
  echo "Create it from env.example: cp env.example .env"
  exit 1
fi

get_env() {
  local key="$1"
  # Docker-style env files allow spaces in values; don't "source" them.
  awk -F= -v k="$key" '$1==k {sub($1"=",""); print; exit}' "${ENV_FILE}"
}

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgres}"

POSTGRES_USER="${POSTGRES_USER:-$(get_env POSTGRES_USER)}"
POSTGRES_DB="${POSTGRES_DB:-$(get_env POSTGRES_DB)}"
POSTGRES_REPL_PASSWORD="${POSTGRES_REPL_PASSWORD:-$(get_env POSTGRES_REPL_PASSWORD)}"

if [[ -z "${POSTGRES_USER}" || -z "${POSTGRES_DB}" ]]; then
  echo "ERROR: POSTGRES_USER and POSTGRES_DB must be set in .env"
  exit 1
fi

REPL_PASSWORD="${POSTGRES_REPL_PASSWORD:-replica_pass}"
if [[ -z "${REPL_PASSWORD}" ]]; then
  echo "ERROR: POSTGRES_REPL_PASSWORD is empty"
  exit 1
fi

echo "[ensure_postgres_replication] Waiting for primary to be ready..."
until docker compose exec -T "${POSTGRES_CONTAINER}" pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; do
  sleep 2
done

echo "[ensure_postgres_replication] Creating/updating replication role..."
docker compose exec -T "${POSTGRES_CONTAINER}" bash -lc "psql -v ON_ERROR_STOP=1 --username '${POSTGRES_USER}' --dbname '${POSTGRES_DB}' <<'EOSQL'
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'replicator') THEN
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '${REPL_PASSWORD}';
  ELSE
    ALTER ROLE replicator WITH PASSWORD '${REPL_PASSWORD}';
  END IF;
END
\$\$;
EOSQL"

echo "[ensure_postgres_replication] Ensuring pg_hba.conf allows replication..."
docker compose exec -T "${POSTGRES_CONTAINER}" bash -lc "HBA='/var/lib/postgresql/data/pg_hba.conf';
grep -qE '^[[:space:]]*host[[:space:]]+replication[[:space:]]+replicator[[:space:]]+0\\.0\\.0\\.0/0' \"\$HBA\" || echo 'host    replication     replicator      0.0.0.0/0               scram-sha-256' >> \"\$HBA\";
grep -qE '^[[:space:]]*host[[:space:]]+replication[[:space:]]+replicator[[:space:]]+::/0' \"\$HBA\" || echo 'host    replication     replicator      ::/0                    scram-sha-256' >> \"\$HBA\";"

echo "[ensure_postgres_replication] Reloading Postgres config..."
docker compose exec -T "${POSTGRES_CONTAINER}" bash -lc "psql -v ON_ERROR_STOP=1 --username '${POSTGRES_USER}' --dbname '${POSTGRES_DB}' -c 'SELECT pg_reload_conf();'"

echo "[ensure_postgres_replication] Done."


