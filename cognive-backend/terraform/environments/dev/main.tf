# =============================================================================
# Cognive Control Plane - Development Environment
# =============================================================================
# This configuration deploys the Cognive stack for local development.
#
# Features:
# - All services running locally with Docker
# - Minimal resource allocation
# - No replicas (single instance)
# - Full monitoring stack enabled
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  # Local backend for dev (state stored locally)
  backend "local" {
    path = "terraform.tfstate"
  }
}

# =============================================================================
# Root Module Call
# =============================================================================

module "cognive" {
  source = "../../"

  # Environment
  environment = "dev"

  # Docker configuration
  docker_host           = var.docker_host
  docker_network_subnet = "172.28.0.0/16"

  # PostgreSQL
  postgres_user            = var.postgres_user
  postgres_password        = var.postgres_password
  postgres_db              = var.postgres_db
  enable_postgres_replicas = false # No replicas in dev
  postgres_memory_limit    = "1g"
  postgres_cpu_limit       = "0.5"

  # Redis
  redis_password           = var.redis_password
  redis_max_memory         = "512mb"
  redis_enable_persistence = true
  redis_enable_replica     = false # No replica in dev
  redis_memory_limit       = "512m"
  redis_cpu_limit          = "0.25"

  # RabbitMQ
  rabbitmq_user                 = var.rabbitmq_user
  rabbitmq_password             = var.rabbitmq_password
  rabbitmq_enable_management_ui = true
  rabbitmq_management_port      = 15672
  rabbitmq_memory_limit         = "512m"
  rabbitmq_cpu_limit            = "0.25"

  # MinIO
  minio_root_user     = var.minio_root_user
  minio_root_password = var.minio_root_password
  minio_api_port      = 9002 # Avoid port conflicts
  minio_console_port  = 9003
  minio_memory_limit  = "256m"
  minio_cpu_limit     = "0.25"
  minio_default_buckets = [
    "cognive-logs",
    "cognive-artifacts",
    "cognive-backups",
  ]

  # Monitoring (enabled for dev)
  enable_monitoring         = var.enable_monitoring
  prometheus_retention_days = 7 # Shorter retention in dev
  prometheus_port           = 9090
  grafana_admin_user        = var.grafana_admin_user
  grafana_admin_password    = var.grafana_admin_password
  grafana_port              = 3000
  enable_loki               = false # Optional in dev
  loki_port                 = 3100
}

# =============================================================================
# Outputs
# =============================================================================

output "services" {
  description = "Service endpoints for development"
  value = {
    postgres = {
      host = module.cognive.postgres_connection.host
      port = module.cognive.postgres_connection.port
      url  = "postgresql://${var.postgres_user}:****@localhost:5432/${var.postgres_db}"
    }
    redis = {
      host = module.cognive.redis_connection.host
      port = module.cognive.redis_connection.port
      url  = "redis://localhost:6379"
    }
    rabbitmq = {
      host           = module.cognive.rabbitmq_connection.host
      port           = module.cognive.rabbitmq_connection.port
      management_url = "http://localhost:15672"
    }
    minio = {
      endpoint    = module.cognive.minio_connection.endpoint
      console_url = "http://localhost:9003"
    }
    monitoring = module.cognive.monitoring_urls
  }
}

output "network_name" {
  description = "Docker network name"
  value       = module.cognive.network_name
}

output "quick_start" {
  description = "Quick start commands"
  value       = <<-EOF
    
    ============================================================
    Cognive Development Environment Ready!
    ============================================================
    
    Services:
    - PostgreSQL:  localhost:5432
    - Redis:       localhost:6379
    - RabbitMQ:    localhost:5672 (UI: http://localhost:15672)
    - MinIO:       localhost:9002 (Console: http://localhost:9003)
    - Prometheus:  http://localhost:9090
    - Grafana:     http://localhost:3000
    
    Run the API:
      cd cognive-backend && docker-compose up api
    
    Connect to PostgreSQL:
      psql postgresql://${var.postgres_user}@localhost:5432/${var.postgres_db}
    
    ============================================================
  EOF
}

