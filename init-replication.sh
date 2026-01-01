#!/bin/bash
set -e

# Create replication user for PostgreSQL streaming replication
# This script runs on the primary during first initialization

REPL_PASSWORD="${POSTGRES_REPL_PASSWORD:-replica_pass}"

if [[ -z "${REPL_PASSWORD}" ]]; then
  echo "ERROR: POSTGRES_REPL_PASSWORD is empty. Set POSTGRES_REPL_PASSWORD in your env file."
  exit 1
fi

echo "Creating replication user 'replicator'..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create replication user if not exists
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'replicator') THEN
            CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '$REPL_PASSWORD';
            RAISE NOTICE 'Created replication user: replicator';
        ELSE
            ALTER ROLE replicator WITH PASSWORD '$REPL_PASSWORD';
            RAISE NOTICE 'Updated password for replication user: replicator';
        END IF;
    END
    \$\$;
EOSQL

# Configure pg_hba.conf for replication access
echo "Configuring pg_hba.conf for replication..."
cat >> /var/lib/postgresql/data/pg_hba.conf <<EOF

# Replication connections
host    replication     replicator      0.0.0.0/0               scram-sha-256
EOF

echo "Reloading PostgreSQL config to apply pg_hba.conf changes..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT pg_reload_conf();
EOSQL

echo "Replication setup complete!"

