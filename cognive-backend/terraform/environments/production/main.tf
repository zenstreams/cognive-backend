# =============================================================================
# Cognive Control Plane - Production Environment
# =============================================================================
# This configuration deploys the Cognive stack for production.
#
# Features:
# - Full high availability configuration
# - Multiple read replicas
# - Complete monitoring and alerting
# - Maximum resource allocation
# - Secure configuration
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  # S3-compatible backend for production (MinIO or AWS S3)
  # REQUIRED: Configure this for production deployments!
  # backend "s3" {
  #   bucket         = "cognive-terraform-state-prod"
  #   key            = "production/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "cognive-terraform-locks"
  #   
  #   # For MinIO backend:
  #   # endpoint                    = "https://minio.cognive.io:9000"
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
  environment = "production"

  # Docker configuration
  docker_host           = var.docker_host
  docker_network_subnet = "172.30.0.0/16"

  # PostgreSQL (HA configuration)
  postgres_user                 = var.postgres_user
  postgres_password             = var.postgres_password
  postgres_db                   = var.postgres_db
  enable_postgres_replicas      = true
  postgres_replica_count        = 2 # 2 replicas for production
  postgres_replication_password = var.postgres_replication_password
  postgres_memory_limit         = "4g"
  postgres_cpu_limit            = "2.0"

  # Redis (HA configuration)
  redis_password           = var.redis_password
  redis_max_memory         = "4gb"
  redis_enable_persistence = true
  redis_enable_replica     = true
  redis_memory_limit       = "2g"
  redis_cpu_limit          = "1.0"

  # RabbitMQ
  rabbitmq_user                 = var.rabbitmq_user
  rabbitmq_password             = var.rabbitmq_password
  rabbitmq_enable_management_ui = true # Consider disabling in high-security environments
  rabbitmq_management_port      = 15672
  rabbitmq_memory_limit         = "2g"
  rabbitmq_cpu_limit            = "1.0"

  # MinIO
  minio_root_user     = var.minio_root_user
  minio_root_password = var.minio_root_password
  minio_api_port      = 9000
  minio_console_port  = 9001
  minio_memory_limit  = "1024m"
  minio_cpu_limit     = "1.0"
  minio_default_buckets = [
    "cognive-logs",
    "cognive-artifacts",
    "cognive-backups",
    "cognive-reports",
    "cognive-audit-logs",
  ]

  # Monitoring (full stack with longer retention)
  enable_monitoring         = true
  prometheus_retention_days = 30 # 30 days retention for production
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
  description = "Service endpoints for production"
  value = {
    postgres = {
      primary  = module.cognive.postgres_connection
      replicas = "See postgres_replica_* outputs"
      note     = "Use read replicas for analytics queries"
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

output "ha_status" {
  description = "High availability status"
  value = {
    postgres_replicas = 2
    redis_replica     = true
    monitoring        = true
    loki_logging      = true
  }
}

output "security_checklist" {
  description = "Production security checklist"
  value       = <<-EOF
    
    ============================================================
    PRODUCTION SECURITY CHECKLIST
    ============================================================
    
    [ ] All passwords are strong and unique
    [ ] TLS/SSL configured for all external endpoints
    [ ] Firewall rules configured (allow only necessary ports)
    [ ] Database backups configured and tested
    [ ] Monitoring alerts configured
    [ ] Log retention policies configured
    [ ] API rate limiting enabled
    [ ] Secrets stored securely (not in tfvars files)
    
    ============================================================
  EOF
}

