# =============================================================================
# Cognive Control Plane - Terraform Root Configuration
# =============================================================================
# This is the root Terraform configuration for the Cognive Control Plane.
# It orchestrates all infrastructure modules for a complete deployment.
#
# Supported Deployment Targets:
# 1. Self-Hosted (Docker/Docker Compose) - Primary/Free
# 2. Oracle Cloud Always Free Tier - $0/month
# 3. AWS Managed Services - Paid alternative
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    # Docker provider for self-hosted/local deployments
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }

    # Random provider for generating secure values
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }

    # Local provider for file operations
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }

    # Null provider for local-exec and triggers
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# =============================================================================
# Local Variables
# =============================================================================

locals {
  # Common tags for all resources
  common_tags = {
    Project     = "cognive"
    Environment = var.environment
    ManagedBy   = "terraform"
    Component   = "control-plane"
  }

  # Network configuration
  network_name = "cognive-${var.environment}"

  # Container image versions (pinned for reproducibility)
  images = {
    postgres   = "timescale/timescaledb:latest-pg15"
    redis      = "redis:7-alpine"
    rabbitmq   = "rabbitmq:3-management"
    minio      = "minio/minio:latest"
    prometheus = "prom/prometheus:v2.48.0"
    grafana    = "grafana/grafana:10.2.0"
    loki       = "grafana/loki:2.9.0"
    traefik    = "traefik:v3.0"
  }
}

# =============================================================================
# Docker Provider Configuration (Self-Hosted)
# =============================================================================

provider "docker" {
  # Use local Docker daemon by default
  # For remote deployment, configure host URL
  host = var.docker_host
}

# =============================================================================
# Docker Network
# =============================================================================

resource "docker_network" "cognive" {
  name   = local.network_name
  driver = "bridge"

  ipam_config {
    subnet  = var.docker_network_subnet
    gateway = var.docker_network_gateway
  }

  labels {
    label = "project"
    value = "cognive"
  }

  labels {
    label = "environment"
    value = var.environment
  }
}

# =============================================================================
# Infrastructure Modules
# =============================================================================

# PostgreSQL with TimescaleDB (Primary Database)
module "postgres" {
  source = "./modules/postgres"

  environment  = var.environment
  network_name = docker_network.cognive.name
  network_id   = docker_network.cognive.id

  # Database configuration
  postgres_user     = var.postgres_user
  postgres_password = var.postgres_password
  postgres_db       = var.postgres_db

  # Replication settings
  enable_replicas      = var.enable_postgres_replicas
  replica_count        = var.postgres_replica_count
  replication_password = var.postgres_replication_password

  # Storage
  data_volume_name = "cognive-postgres-data-${var.environment}"

  # Resource limits
  memory_limit = var.postgres_memory_limit
  cpu_limit    = var.postgres_cpu_limit

  common_tags = local.common_tags
}

# Redis (Cache Layer)
module "redis" {
  source = "./modules/redis"

  environment  = var.environment
  network_name = docker_network.cognive.name
  network_id   = docker_network.cognive.id

  # Redis configuration
  redis_password = var.redis_password
  max_memory     = var.redis_max_memory

  # Persistence
  enable_persistence = var.redis_enable_persistence
  data_volume_name   = "cognive-redis-data-${var.environment}"

  # High availability
  enable_replica = var.redis_enable_replica

  # Resource limits
  memory_limit = var.redis_memory_limit
  cpu_limit    = var.redis_cpu_limit

  common_tags = local.common_tags
}

# RabbitMQ (Message Queue)
module "rabbitmq" {
  source = "./modules/rabbitmq"

  environment  = var.environment
  network_name = docker_network.cognive.name
  network_id   = docker_network.cognive.id

  # RabbitMQ configuration
  rabbitmq_user     = var.rabbitmq_user
  rabbitmq_password = var.rabbitmq_password

  # Storage
  data_volume_name = "cognive-rabbitmq-data-${var.environment}"

  # Resource limits
  memory_limit = var.rabbitmq_memory_limit
  cpu_limit    = var.rabbitmq_cpu_limit

  # Management UI
  enable_management_ui = var.rabbitmq_enable_management_ui
  management_port      = var.rabbitmq_management_port

  common_tags = local.common_tags
}

# MinIO (S3-Compatible Object Storage)
module "minio" {
  source = "./modules/minio"

  environment  = var.environment
  network_name = docker_network.cognive.name
  network_id   = docker_network.cognive.id

  # MinIO configuration
  root_user     = var.minio_root_user
  root_password = var.minio_root_password

  # Storage
  data_volume_name = "cognive-minio-data-${var.environment}"

  # Ports
  api_port     = var.minio_api_port
  console_port = var.minio_console_port

  # Resource limits
  memory_limit = var.minio_memory_limit
  cpu_limit    = var.minio_cpu_limit

  # Default buckets to create
  default_buckets = var.minio_default_buckets

  common_tags = local.common_tags
}

# Monitoring Stack (Prometheus + Grafana + Loki)
module "monitoring" {
  source = "./modules/monitoring"

  count = var.enable_monitoring ? 1 : 0

  environment  = var.environment
  network_name = docker_network.cognive.name
  network_id   = docker_network.cognive.id

  # Prometheus configuration
  prometheus_retention_days = var.prometheus_retention_days
  prometheus_port           = var.prometheus_port

  # Grafana configuration
  grafana_admin_user     = var.grafana_admin_user
  grafana_admin_password = var.grafana_admin_password
  grafana_port           = var.grafana_port

  # Loki configuration
  enable_loki = var.enable_loki
  loki_port   = var.loki_port

  # Storage volumes
  prometheus_volume = "cognive-prometheus-data-${var.environment}"
  grafana_volume    = "cognive-grafana-data-${var.environment}"
  loki_volume       = "cognive-loki-data-${var.environment}"

  # Targets to scrape
  scrape_targets = [
    {
      job_name = "cognive-api"
      targets  = ["api:8000"]
    }
  ]

  common_tags = local.common_tags
}

# =============================================================================
# Outputs are defined in outputs.tf
# =============================================================================
