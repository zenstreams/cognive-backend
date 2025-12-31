# =============================================================================
# PostgreSQL + TimescaleDB Module
# =============================================================================
# This module provisions PostgreSQL with TimescaleDB extension for the
# Cognive Control Plane database layer.
#
# Features:
# - PostgreSQL 15 with TimescaleDB extension
# - Streaming replication support (optional replicas)
# - Connection health checks
# - WAL-level configuration for replication
# - Automatic initialization scripts
# =============================================================================

terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# =============================================================================
# Local Variables
# =============================================================================

locals {
  container_name         = "cognive-postgres-${var.environment}"
  replica_container_base = "cognive-postgres-replica-${var.environment}"
  image                  = "timescale/timescaledb:latest-pg15"

  # Parse memory limit with m or g suffix
  memory_bytes = var.memory_limit != "" ? (
    can(regex("g$", lower(var.memory_limit))) ?
    parseint(replace(lower(var.memory_limit), "g", ""), 10) * 1024 * 1024 * 1024 :
    can(regex("m$", lower(var.memory_limit))) ?
    parseint(replace(lower(var.memory_limit), "m", ""), 10) * 1024 * 1024 :
    null
  ) : null

  # PostgreSQL configuration parameters
  postgres_config = [
    # TimescaleDB and statistics
    "-c", "shared_preload_libraries=timescaledb,pg_stat_statements",
    "-c", "pg_stat_statements.track=all",
    "-c", "pg_stat_statements.max=10000",
    # Replication settings
    "-c", "wal_level=replica",
    "-c", "max_wal_senders=10",
    "-c", "max_replication_slots=10",
    "-c", "wal_keep_size=256MB",
    "-c", "hot_standby=on",
    # Performance tuning
    "-c", "shared_buffers=256MB",
    "-c", "effective_cache_size=768MB",
    "-c", "work_mem=16MB",
    "-c", "maintenance_work_mem=128MB",
  ]
}

# =============================================================================
# Generate Replication Password if not provided
# =============================================================================

resource "random_password" "replication_password" {
  count   = var.enable_replicas && var.replication_password == "" ? 1 : 0
  length  = 32
  special = false
}

locals {
  replication_password = var.enable_replicas ? (
    var.replication_password != "" ? var.replication_password : random_password.replication_password[0].result
  ) : ""
}

# =============================================================================
# Docker Volume for Primary
# =============================================================================

resource "docker_volume" "postgres_data" {
  name = var.data_volume_name

  labels {
    label = "project"
    value = "cognive"
  }

  labels {
    label = "environment"
    value = var.environment
  }

  labels {
    label = "component"
    value = "postgres-primary"
  }
}

# =============================================================================
# PostgreSQL Primary Container
# =============================================================================

resource "docker_image" "postgres" {
  name         = local.image
  keep_locally = true
}

resource "docker_container" "postgres_primary" {
  name  = local.container_name
  image = docker_image.postgres.image_id

  restart = "unless-stopped"

  # Environment variables
  env = [
    "POSTGRES_USER=${var.postgres_user}",
    "POSTGRES_PASSWORD=${var.postgres_password}",
    "POSTGRES_DB=${var.postgres_db}",
    "POSTGRES_INITDB_ARGS=--data-checksums",
  ]

  # Command with configuration
  command = concat(["postgres"], local.postgres_config)

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "postgres",
      "postgres-primary",
      local.container_name,
    ]
  }

  # Port mapping
  ports {
    internal = 5432
    external = var.primary_external_port
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.postgres_data.name
    container_path = "/var/lib/postgresql/data"
  }

  # Health check
  healthcheck {
    test         = ["CMD-SHELL", "pg_isready -U ${var.postgres_user} -d ${var.postgres_db}"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 5
    start_period = "30s"
  }

  # Resource limits
  memory = local.memory_bytes

  # Labels
  labels {
    label = "project"
    value = "cognive"
  }

  labels {
    label = "environment"
    value = var.environment
  }

  labels {
    label = "component"
    value = "postgres-primary"
  }
}

# =============================================================================
# Replication Bootstrap (Creates replication user + pg_hba entry)
# =============================================================================
#
# NOTE:
# - Postgres init scripts only run on first database init, and the docker provider
#   doesn't reliably support mounting init scripts across platforms.
# - Instead, we bootstrap replication *after* the primary is up using `docker exec`.
#
resource "null_resource" "configure_replication" {
  count = var.enable_replicas ? 1 : 0

  triggers = {
    primary_container_id  = docker_container.postgres_primary.id
    replication_password  = local.replication_password
    postgres_user         = var.postgres_user
    postgres_db           = var.postgres_db
  }

  provisioner "local-exec" {
    command = <<-EOF
      set -euo pipefail

      echo "Waiting for PostgreSQL primary to become ready..."
      for i in $(seq 1 60); do
        if docker exec ${local.container_name} sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1'; then
          break
        fi
        sleep 2
      done

      echo "Ensuring replication role exists..."
      docker exec ${local.container_name} sh -lc '
        set -euo pipefail
        export PGPASSWORD="$POSTGRES_PASSWORD"
        psql -v ON_ERROR_STOP=1 \
          -v repl_pass="${local.replication_password}" \
          --username "$POSTGRES_USER" \
          --dbname "$POSTGRES_DB" \
          -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ''replicator'') THEN CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD :''repl_pass''; END IF; END \$\$;"
      '

      echo "Ensuring pg_hba.conf allows replication connections..."
      docker exec ${local.container_name} sh -lc '
        set -euo pipefail
        file="/var/lib/postgresql/data/pg_hba.conf"
        line="host replication replicator 0.0.0.0/0 scram-sha-256"
        grep -qF "$line" "$file" || echo "$line" >> "$file"
        pg_ctl reload -D /var/lib/postgresql/data
      '

      echo "Replication bootstrap complete."
    EOF
  }

  depends_on = [docker_container.postgres_primary]
}

# =============================================================================
# PostgreSQL Replica Containers
# =============================================================================

resource "docker_volume" "postgres_replica_data" {
  count = var.enable_replicas ? var.replica_count : 0
  name  = "cognive-postgres-replica-${count.index + 1}-data-${var.environment}"

  labels {
    label = "project"
    value = "cognive"
  }

  labels {
    label = "environment"
    value = var.environment
  }

  labels {
    label = "component"
    value = "postgres-replica-${count.index + 1}"
  }
}

resource "docker_container" "postgres_replica" {
  count = var.enable_replicas ? var.replica_count : 0

  name  = "${local.replica_container_base}-${count.index + 1}"
  image = docker_image.postgres.image_id

  restart = "unless-stopped"

  # Environment variables
  env = [
    "PGUSER=replicator",
    "PGPASSWORD=${local.replication_password}",
    "PGDATA=/var/lib/postgresql/data",
  ]

  # Entrypoint to initialize replica from primary
  entrypoint = ["/bin/bash", "-c"]
  command = [<<-EOF
    set -e
    if [ ! -f /var/lib/postgresql/data/PG_VERSION ]; then
      echo "Initializing replica from primary..."
      until pg_isready -h ${local.container_name} -p 5432; do
        echo "Waiting for primary..."
        sleep 2
      done
      rm -rf /var/lib/postgresql/data/*
      PGPASSWORD=$PGPASSWORD pg_basebackup -h ${local.container_name} -D /var/lib/postgresql/data -U replicator -Fp -Xs -P -R
      chmod 700 /var/lib/postgresql/data
    fi
    exec postgres -c hot_standby=on -c shared_preload_libraries=timescaledb
  EOF
  ]

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "postgres-replica-${count.index + 1}",
      "${local.replica_container_base}-${count.index + 1}",
    ]
  }

  # Port mapping (offset from primary)
  ports {
    internal = 5432
    external = var.primary_external_port + count.index + 1
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.postgres_replica_data[count.index].name
    container_path = "/var/lib/postgresql/data"
  }

  # Health check
  healthcheck {
    test         = ["CMD-SHELL", "pg_isready"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 5
    start_period = "60s"
  }

  # Resource limits
  memory = local.memory_bytes

  # Depends on primary
  depends_on = [
    docker_container.postgres_primary,
    null_resource.configure_replication,
  ]

  # Labels
  labels {
    label = "project"
    value = "cognive"
  }

  labels {
    label = "environment"
    value = var.environment
  }

  labels {
    label = "component"
    value = "postgres-replica-${count.index + 1}"
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "primary_host" {
  description = "PostgreSQL primary container hostname"
  value       = local.container_name
}

output "primary_port" {
  description = "PostgreSQL primary external port"
  value       = var.primary_external_port
}

output "replica_hosts" {
  description = "PostgreSQL replica container hostnames"
  value       = var.enable_replicas ? [for i in range(var.replica_count) : "${local.replica_container_base}-${i + 1}"] : []
}

output "replica_ports" {
  description = "PostgreSQL replica external ports"
  value       = var.enable_replicas ? [for i in range(var.replica_count) : var.primary_external_port + i + 1] : []
}

output "connection_string" {
  description = "PostgreSQL connection string (primary)"
  value       = "postgresql://${var.postgres_user}:${var.postgres_password}@${local.container_name}:5432/${var.postgres_db}"
  sensitive   = true
}

output "async_connection_string" {
  description = "PostgreSQL async connection string (primary)"
  value       = "postgresql+asyncpg://${var.postgres_user}:${var.postgres_password}@${local.container_name}:5432/${var.postgres_db}"
  sensitive   = true
}

output "replication_password" {
  description = "PostgreSQL replication password"
  value       = local.replication_password
  sensitive   = true
}

output "volume_name" {
  description = "PostgreSQL data volume name"
  value       = docker_volume.postgres_data.name
}

