# =============================================================================
# Cognive Control Plane - Oracle Cloud Always Free Environment
# =============================================================================
# This configuration deploys the Cognive stack on Oracle Cloud Always Free.
#
# Resources used (all free forever):
# - VM.Standard.A1.Flex: 4 ARM cores, 24GB RAM
# - 200GB Block Storage
# - 10GB Object Storage (for Terraform state)
# - 10TB/month outbound transfer
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  # Oracle Object Storage backend (S3-compatible)
  # Uncomment and configure after creating the bucket
  # backend "s3" {
  #   bucket   = "cognive-terraform-state"
  #   key      = "oracle-free/terraform.tfstate"
  #   region   = "us-ashburn-1"  # Your OCI region
  #   
  #   # Oracle Object Storage S3-compatible endpoint
  #   # Format: https://<namespace>.compat.objectstorage.<region>.oraclecloud.com
  #   endpoint = "https://YOUR_NAMESPACE.compat.objectstorage.us-ashburn-1.oraclecloud.com"
  #   
  #   skip_credentials_validation = true
  #   skip_metadata_api_check     = true
  #   skip_region_validation      = true
  #   force_path_style            = true
  # }

  backend "local" {
    path = "terraform.tfstate"
  }
}

# =============================================================================
# Root Module Call - Optimized for Oracle Cloud ARM
# =============================================================================

module "cognive" {
  source = "../../"

  # Environment
  environment = "oracle-free"

  # Docker configuration (running on ARM64 Oracle instance)
  docker_host           = var.docker_host
  docker_network_subnet = "172.28.0.0/16"

  # PostgreSQL - generous allocation on 24GB instance
  postgres_user                 = var.postgres_user
  postgres_password             = var.postgres_password
  postgres_db                   = var.postgres_db
  enable_postgres_replicas      = true # Can afford replicas with 24GB RAM!
  postgres_replica_count        = 1
  postgres_replication_password = var.postgres_replication_password
  postgres_memory_limit         = "4g" # 4GB for primary
  postgres_cpu_limit            = "1.0"

  # Redis - with persistence and replica
  redis_password           = var.redis_password
  redis_max_memory         = "2gb"
  redis_enable_persistence = true
  redis_enable_replica     = true # HA enabled
  redis_memory_limit       = "2g"
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
  ]

  # Monitoring - full stack enabled (we have the resources!)
  enable_monitoring         = true
  prometheus_retention_days = 30 # 30 days retention
  prometheus_port           = 9090
  grafana_admin_user        = var.grafana_admin_user
  grafana_admin_password    = var.grafana_admin_password
  grafana_port              = 3000
  enable_loki               = true # Enable log aggregation
  loki_port                 = 3100
}

# =============================================================================
# Outputs
# =============================================================================

output "deployment_info" {
  description = "Oracle Cloud deployment information"
  value       = <<-EOF
    
    ============================================================
    🆓 Cognive on Oracle Cloud Always Free
    ============================================================
    
    Infrastructure Cost: $0/month (forever!)
    
    Resources Used:
    - Compute: VM.Standard.A1.Flex (4 ARM cores, 24GB RAM)
    - Storage: Block Volume (100GB boot + data volumes)
    - Network: 10TB outbound/month included
    
    Services Running:
    - PostgreSQL: localhost:5432 (with 1 replica)
    - Redis:      localhost:6379 (with replica)
    - RabbitMQ:   localhost:5672 (UI: http://<public-ip>:15672)
    - MinIO:      localhost:9000 (Console: http://<public-ip>:9001)
    - Prometheus: http://<public-ip>:9090
    - Grafana:    http://<public-ip>:3000
    
    Next Steps:
    1. Configure firewall rules in OCI Security List
    2. Set up SSL with Let's Encrypt
    3. Configure DNS (optional)
    
    ============================================================
  EOF
}

output "services" {
  description = "Service connection details"
  value = {
    postgres   = module.cognive.postgres_connection
    redis      = module.cognive.redis_connection
    rabbitmq   = module.cognive.rabbitmq_connection
    minio      = module.cognive.minio_connection
    monitoring = module.cognive.monitoring_urls
  }
}

output "firewall_rules_needed" {
  description = "Ports to open in OCI Security List"
  value       = <<-EOF
    
    Open these ports in your OCI Security List (VCN → Security Lists):
    
    | Port  | Protocol | Purpose           | Source     |
    |-------|----------|-------------------|------------|
    | 22    | TCP      | SSH               | Your IP    |
    | 80    | TCP      | HTTP              | 0.0.0.0/0  |
    | 443   | TCP      | HTTPS             | 0.0.0.0/0  |
    | 8000  | TCP      | Cognive API       | 0.0.0.0/0  |
    | 3000  | TCP      | Grafana (optional)| Your IP    |
    | 9090  | TCP      | Prometheus (opt)  | Your IP    |
    | 15672 | TCP      | RabbitMQ UI (opt) | Your IP    |
    
  EOF
}

