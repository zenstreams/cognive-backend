#!/usr/bin/env bash
set -euo pipefail

# Local dev bootstrap:
# - brings up core services
# - ensures Postgres replication is configured (even on existing volumes)
# - starts replicas + API

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo "[dev-up] .env missing, creating from env.example"
  cp env.example .env
fi

echo "[dev-up] Starting core services..."
docker compose up -d --build postgres redis rabbitmq minio

echo "[dev-up] Stopping replicas (if running) to avoid restart loop..."
docker compose stop postgres_replica_1 postgres_replica_2 >/dev/null 2>&1 || true

echo "[dev-up] Ensuring Postgres replication config..."
bash "${ROOT_DIR}/scripts/ensure_postgres_replication.sh"

echo "[dev-up] Starting replicas + API..."
docker compose up -d postgres_replica_1 postgres_replica_2 api

echo "[dev-up] Ensuring local Kong TLS certs..."
bash "${ROOT_DIR}/scripts/generate_local_kong_tls.sh"

echo "[dev-up] Starting Kong API gateway..."
docker compose up -d kong

echo "[dev-up] Current status:"
docker compose ps


