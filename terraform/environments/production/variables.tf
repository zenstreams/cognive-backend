# =============================================================================
# Production Environment Variables
# =============================================================================
# IMPORTANT: For production, use a secrets management solution like:
# - HashiCorp Vault
# - AWS Secrets Manager
# - Environment variables from CI/CD
# 
# DO NOT store production credentials in terraform.tfvars files!
# =============================================================================

variable "docker_host" {
  description = "Docker host URL"
  type        = string
  default     = "unix:///var/run/docker.sock"
}

# PostgreSQL
variable "postgres_user" {
  description = "PostgreSQL username"
  type        = string
  default     = "cognive"
}

variable "postgres_password" {
  description = "PostgreSQL password (use secrets manager in production)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.postgres_password) >= 16
    error_message = "Production PostgreSQL password must be at least 16 characters."
  }
}

variable "postgres_db" {
  description = "PostgreSQL database name"
  type        = string
  default     = "cognive"
}

variable "postgres_replication_password" {
  description = "PostgreSQL replication password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.postgres_replication_password) >= 16
    error_message = "Production replication password must be at least 16 characters."
  }
}

# Redis
variable "redis_password" {
  description = "Redis password (required in production)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.redis_password) >= 16
    error_message = "Production Redis password must be at least 16 characters."
  }
}

# RabbitMQ
variable "rabbitmq_user" {
  description = "RabbitMQ username"
  type        = string
  default     = "cognive"
}

variable "rabbitmq_password" {
  description = "RabbitMQ password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.rabbitmq_password) >= 16
    error_message = "Production RabbitMQ password must be at least 16 characters."
  }
}

# MinIO
variable "minio_root_user" {
  description = "MinIO root user"
  type        = string
  default     = "cognive"
}

variable "minio_root_password" {
  description = "MinIO root password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.minio_root_password) >= 16
    error_message = "Production MinIO password must be at least 16 characters."
  }
}

# Monitoring
variable "grafana_admin_user" {
  description = "Grafana admin username"
  type        = string
  default     = "admin"
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.grafana_admin_password) >= 12
    error_message = "Production Grafana password must be at least 12 characters."
  }
}

