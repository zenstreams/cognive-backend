# =============================================================================
# Development Environment Variables
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
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "postgres_db" {
  description = "PostgreSQL database name"
  type        = string
  default     = "cognive"
}

# Redis
variable "redis_password" {
  description = "Redis password"
  type        = string
  sensitive   = true
  default     = ""
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
}

# Monitoring
variable "enable_monitoring" {
  description = "Enable monitoring stack"
  type        = bool
  default     = true
}

variable "grafana_admin_user" {
  description = "Grafana admin username"
  type        = string
  default     = "admin"
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
  default     = "admin"
}

