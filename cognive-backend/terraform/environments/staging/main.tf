# =============================================================================
# Cognive Control Plane - Staging Environment
# =============================================================================
# This configuration deploys the Cognive stack for staging/testing.
#
# Features:
# - Production-like configuration
# - Read replicas enabled
# - Full monitoring stack
# - Higher resource allocation
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  # S3-compatible backend for staging (MinIO or S3)
  # Uncomment and configure when ready
  # backend "s3" {
  #   bucket         = "cognive-terraform-state"
  #   key            = "staging/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "cognive-terraform-locks"
  #   
  #   # For MinIO, use these additional settings:
  #   # endpoint                    = "http://minio.example.com:9000"
  #   # skip_credentials_validation = true
  #   # skip_metadata_api_check     = true
  #   # force_path_style            = true
  # }

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
  environment = "staging"

  # Docker configuration
  docker_host           = var.docker_host
  docker_network_subnet = "172.29.0.0/16"

  # PostgreSQL (with replicas)
  postgres_user                 = var.postgres_user
  postgres_password             = var.postgres_password
  postgres_db                   = var.postgres_db
  enable_postgres_replicas      = true
  postgres_replica_count        = 1 # 1 replica for staging
  postgres_replication_password = var.postgres_replication_password
  postgres_memory_limit         = "2g"
  postgres_cpu_limit            = "1.0"

  # Redis (with replica)
  redis_password           = var.redis_password
  redis_max_memory         = "2gb"
  redis_enable_persistence = true
  redis_enable_replica     = true
  redis_memory_limit       = "1g"
  redis_cpu_limit          = "0.5"

  # RabbitMQ
  rabbitmq_user                 = var.rabbitmq_user
  rabbitmq_password             = var.rabbitmq_password
  rabbitmq_enable_management_ui = true
  rabbitmq_management_port      = 15672
  rabbitmq_memory_limit         = "1g"
  rabbitmq_cpu_limit            = "0.5"

  # MinIO
  minio_root_user     = var.minio_root_user
  minio_root_password = var.minio_root_password
  minio_api_port      = 9000
  minio_console_port  = 9001
  minio_memory_limit  = "512m"
  minio_cpu_limit     = "0.5"
  minio_default_buckets = [
    "cognive-logs",
    "cognive-artifacts",
    "cognive-backups",
    "cognive-reports",
  ]

  # Monitoring (full stack)
  enable_monitoring         = true
  prometheus_retention_days = 15
  prometheus_port           = 9090
  grafana_admin_user        = var.grafana_admin_user
  grafana_admin_password    = var.grafana_admin_password
  grafana_port              = 3000
  enable_loki               = true
  loki_port                 = 3100
}

# =============================================================================
# Outputs
# =============================================================================

output "services" {
  description = "Service endpoints for staging"
  value = {
    postgres = {
      primary  = module.cognive.postgres_connection
      replicas = "See postgres_replica_* outputs"
    }
    redis      = module.cognive.redis_connection
    rabbitmq   = module.cognive.rabbitmq_connection
    minio      = module.cognive.minio_connection
    monitoring = module.cognive.monitoring_urls
  }
}

output "network_name" {
  description = "Docker network name"
  value       = module.cognive.network_name
}

