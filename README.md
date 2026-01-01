# Cognive Control Plane Backend

FastAPI-based backend aligned with the control plane architecture. This folder can be used as a standalone repository.

## Quick start (local dev)
1. Copy environment template and adjust secrets:
   ```bash
   cp env.example .env
   ```
2. Bootstrap local dev (starts deps, replicas, API, and Kong gateway with local TLS):
   ```bash
   ./scripts/dev-up.sh
   ```
3. Verify health:
   - Via gateway (HTTP): http://localhost:8000/v1/health/liveness
   - Via gateway (HTTPS): https://localhost:8443/v1/health/liveness
   - Direct API (debug): http://localhost:8002/api/v1/health/liveness
4. API docs:
   - Via gateway (HTTP): http://localhost:8000/v1/docs
   - Direct API (debug): http://localhost:8002/docs

## Services (docker-compose)
- FastAPI API (`api`)
- Kong API Gateway (DB-less) (`kong`)
- PostgreSQL 15 / TimescaleDB primary (`postgres`)
- PostgreSQL read replicas (`postgres_replica_1`, `postgres_replica_2`)
- Redis 7 (`redis`)
- RabbitMQ with management UI (`rabbitmq`, UI at http://localhost:15672)
- MinIO object storage (`minio`, console at http://localhost:9003)

## API Gateway (Kong) (SCRUM-87)
- **Gateway HTTP**: `http://localhost:8000`
- **Gateway HTTPS**: `https://localhost:8443` (self-signed cert generated under `.local/`)
- **Admin API (localhost-only)**: `http://127.0.0.1:8001`
- **API versioning**: `/v1/*` and `/v2/*` are supported at the gateway (currently both route to the app’s `/api/v1/*`)

### Rate limiting (local)
Kong rate limiting is enabled with a simple local policy (per-client-IP).

Example (should return `200` until the limit is exceeded, then `429`):
```bash
curl -i http://localhost:8000/v1/health/liveness
```

HTTPS example (self-signed; `-k` skips trust validation):
```bash
curl -k -i https://localhost:8443/v1/health/liveness
```

## Tech stack
- Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.x
- Celery 5.x, Redis 7, PostgreSQL 15
- MinIO (S3-compatible), RabbitMQ

## Notes
- `.env` is excluded; use `env.example` as a template.
- The `docs/` folder at repo root holds product/architecture documents separate from this backend.

## PostgreSQL read replicas (SCRUM-58)

This stack supports 1-2 read replicas using PostgreSQL streaming replication.

- **Primary**: `postgres:5432`
- **Replicas**: `postgres_replica_1:5432`, `postgres_replica_2:5432`
- **Replication user**: `replicator` (created by `init-replication.sh` on first init)

### Read/write splitting (application)

The app supports read replica routing via environment variables:

- **Writes (primary)**: `DATABASE_URL` / `DATABASE_URL_ASYNC`
- **Reads (replicas)**: `DATABASE_READ_URLS` / `DATABASE_READ_URLS_ASYNC` (comma-separated)

In code, use:
- `app.core.database.get_db()` / `get_async_db()` for **writes**
- `app.core.database.get_db_read()` / `get_async_db_read()` for **read-preferred** queries

### Replication lag monitoring

Call:
- `GET /api/v1/health/replication`

This reports:
- Whether the primary is incorrectly running in recovery mode
- Replica recovery status + estimated lag via `pg_last_xact_replay_timestamp()`

### Failover procedure (manual, local/self-hosted)

This repo does **not** implement automatic failover. For manual failover:

1. **Pick a healthy replica** (low lag) using `GET /api/v1/health/replication`.
2. **Promote the replica** (run inside the replica container):
   ```bash
   docker compose exec postgres_replica_1 pg_ctl -D /var/lib/postgresql/data promote
   ```
3. **Point the API to the promoted node**:
   - Update `.env` `DATABASE_URL` / `DATABASE_URL_ASYNC` to the promoted host (e.g. `postgres_replica_1`)
   - Restart the API container
4. **Rebuild replication topology**:
   - Replace/repair the old primary and re-seed as a replica (requires reinitializing data dir + `pg_basebackup`)

## Database migrations (Alembic)
- Set `DATABASE_URL` in your `.env` (the template in `env.example` points to the dockerized TimescaleDB instance).
- Create a new migration from SQLAlchemy models:
  ```bash
  alembic revision --autogenerate -m "short description"
  ```
- Apply migrations:
  ```bash
  alembic upgrade head
  ```
- Roll back the last migration:
  ```bash
  alembic downgrade -1
  ```
- Run inside docker compose (dev parity):
  ```bash
  docker compose exec api alembic upgrade head
  docker compose exec api alembic downgrade -1
  ```
- Staging/prod: set `DATABASE_URL` to the target Postgres/Timescale instance and run the same commands (no code changes needed).

