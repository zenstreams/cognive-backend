# =============================================================================
# Cognive Control Plane - Terraform Outputs
# =============================================================================
# These outputs provide connection details and useful information about
# the deployed infrastructure.
# =============================================================================

# =============================================================================
# Network Outputs
# =============================================================================

output "docker_network" {
  description = "Docker network configuration"
  value = {
    name = docker_network.cognive.name
    id   = docker_network.cognive.id
  }
}

output "network_name" {
  description = "Docker network name for the Cognive stack"
  value       = docker_network.cognive.name
}

# =============================================================================
# PostgreSQL Outputs
# =============================================================================

output "postgres_primary" {
  description = "PostgreSQL primary connection details"
  value = {
    host     = module.postgres.primary_host
    port     = module.postgres.primary_port
    database = var.postgres_db
    user     = var.postgres_user
  }
}

# Alias for backward compatibility
output "postgres_connection" {
  description = "PostgreSQL connection details (alias)"
  value = {
    host     = module.postgres.primary_host
    port     = module.postgres.primary_port
    database = var.postgres_db
    user     = var.postgres_user
  }
}

output "postgres_replicas" {
  description = "PostgreSQL replica connection details"
  value = var.enable_postgres_replicas ? {
    hosts = module.postgres.replica_hosts
    ports = module.postgres.replica_ports
  } : null
}

output "postgres_connection_string" {
  description = "PostgreSQL connection string for primary (use for writes)"
  value       = module.postgres.connection_string
  sensitive   = true
}

output "postgres_async_connection_string" {
  description = "PostgreSQL async connection string (for asyncpg)"
  value       = module.postgres.async_connection_string
  sensitive   = true
}

# =============================================================================
# Redis Outputs
# =============================================================================

output "redis" {
  description = "Redis connection details"
  value = {
    host         = module.redis.host
    port         = module.redis.port
    replica_host = module.redis.replica_host
    replica_port = module.redis.replica_port
  }
}

# Alias for backward compatibility
output "redis_connection" {
  description = "Redis connection details (alias)"
  value = {
    host = module.redis.host
    port = module.redis.port
  }
}

output "redis_connection_url" {
  description = "Redis connection URL"
  value       = module.redis.connection_url
  sensitive   = true
}

# =============================================================================
# RabbitMQ Outputs
# =============================================================================

output "rabbitmq" {
  description = "RabbitMQ connection details"
  value = {
    host            = module.rabbitmq.host
    port            = module.rabbitmq.port
    management_port = module.rabbitmq.management_port
    management_url  = module.rabbitmq.management_url
    user            = var.rabbitmq_user
  }
}

# Alias for backward compatibility
output "rabbitmq_connection" {
  description = "RabbitMQ connection details (alias)"
  value = {
    host            = module.rabbitmq.host
    port            = module.rabbitmq.port
    management_port = module.rabbitmq.management_port
    user            = var.rabbitmq_user
  }
}

output "rabbitmq_amqp_url" {
  description = "RabbitMQ AMQP connection URL"
  value       = module.rabbitmq.amqp_url
  sensitive   = true
}

# =============================================================================
# MinIO Outputs
# =============================================================================

output "minio" {
  description = "MinIO connection details"
  value = {
    host        = module.minio.host
    endpoint    = module.minio.endpoint
    api_port    = module.minio.api_port
    console_url = module.minio.console_url
  }
}

# Alias for backward compatibility
output "minio_connection" {
  description = "MinIO connection details (alias)"
  value = {
    endpoint     = module.minio.endpoint
    api_port     = module.minio.api_port
    console_port = module.minio.console_port
  }
}

output "minio_credentials" {
  description = "MinIO credentials"
  value = {
    access_key = module.minio.access_key
    secret_key = module.minio.secret_key
  }
  sensitive = true
}

# =============================================================================
# Monitoring Outputs
# =============================================================================

output "monitoring" {
  description = "Monitoring stack URLs"
  value = var.enable_monitoring ? {
    prometheus = module.monitoring[0].prometheus_url
    grafana    = module.monitoring[0].grafana_url
    loki       = module.monitoring[0].loki_url
  } : null
}

# Alias for backward compatibility
output "monitoring_urls" {
  description = "Monitoring stack URLs (alias)"
  value = var.enable_monitoring ? {
    prometheus = "http://localhost:${var.prometheus_port}"
    grafana    = "http://localhost:${var.grafana_port}"
    loki       = var.enable_loki ? "http://localhost:${var.loki_port}" : null
  } : null
}

# =============================================================================
# Environment Configuration Export
# =============================================================================

output "env_file_content" {
  description = "Content for .env file (sensitive)"
  value       = <<-EOF
# Cognive Control Plane Environment Variables
# Generated by Terraform for environment: ${var.environment}
# Generated at: ${timestamp()}

# Database
DATABASE_URL=postgresql://${var.postgres_user}:${var.postgres_password}@${module.postgres.primary_host}:5432/${var.postgres_db}
DATABASE_URL_ASYNC=postgresql+asyncpg://${var.postgres_user}:${var.postgres_password}@${module.postgres.primary_host}:5432/${var.postgres_db}
POSTGRES_USER=${var.postgres_user}
POSTGRES_PASSWORD=${var.postgres_password}
POSTGRES_DB=${var.postgres_db}

# Redis
REDIS_URL=redis://${var.redis_password != "" ? ":${var.redis_password}@" : ""}${module.redis.host}:6379

# RabbitMQ
RABBITMQ_URL=amqp://${var.rabbitmq_user}:${var.rabbitmq_password}@${module.rabbitmq.host}:5672/
RABBITMQ_USER=${var.rabbitmq_user}
RABBITMQ_PASSWORD=${var.rabbitmq_password}

# MinIO
MINIO_ENDPOINT=${module.minio.endpoint}
MINIO_ROOT_USER=${var.minio_root_user}
MINIO_ROOT_PASSWORD=${var.minio_root_password}

# Environment
ENVIRONMENT=${var.environment}
EOF
  sensitive   = true
}

# =============================================================================
# Quick Reference
# =============================================================================

output "quick_reference" {
  description = "Quick reference for accessing services"
  value       = <<-EOF

============================================================
Cognive Control Plane - ${upper(var.environment)} Environment
============================================================

Services:
---------
PostgreSQL:  ${module.postgres.primary_host}:5432
Redis:       ${module.redis.host}:6379
RabbitMQ:    ${module.rabbitmq.host}:5672
MinIO:       ${module.minio.host}:${module.minio.api_port}

Web UIs:
--------
RabbitMQ:    http://localhost:${var.rabbitmq_management_port}
MinIO:       http://localhost:${module.minio.console_port}
${var.enable_monitoring ? "Prometheus:  http://localhost:${var.prometheus_port}" : ""}
${var.enable_monitoring ? "Grafana:     http://localhost:${var.grafana_port}" : ""}

Docker Network: ${docker_network.cognive.name}

Next Steps:
-----------
1. Copy .env file: terraform output -raw env_file_content > ../../.env
2. Start the API: cd ../.. && docker-compose up api
3. Run migrations: docker-compose exec api alembic upgrade head

============================================================
EOF
}

