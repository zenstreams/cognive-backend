# =============================================================================
# Cognive Control Plane - Terraform Variables
# =============================================================================

# =============================================================================
# General Settings
# =============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "docker_host" {
  description = "Docker host URL (default: local Docker daemon)"
  type        = string
  default     = "unix:///var/run/docker.sock"
}

variable "docker_network_subnet" {
  description = "Docker network subnet CIDR"
  type        = string
  default     = "172.28.0.0/16"
}

variable "docker_network_gateway" {
  description = "Docker network gateway IP"
  type        = string
  default     = "172.28.0.1"
}

# =============================================================================
# PostgreSQL Configuration
# =============================================================================

variable "postgres_user" {
  description = "PostgreSQL admin username"
  type        = string
  default     = "cognive"
}

variable "postgres_password" {
  description = "PostgreSQL admin password"
  type        = string
  sensitive   = true
}

variable "postgres_db" {
  description = "PostgreSQL database name"
  type        = string
  default     = "cognive"
}

variable "enable_postgres_replicas" {
  description = "Enable PostgreSQL read replicas"
  type        = bool
  default     = false
}

variable "postgres_replica_count" {
  description = "Number of PostgreSQL read replicas"
  type        = number
  default     = 2
}

variable "postgres_replication_password" {
  description = "PostgreSQL replication user password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "postgres_memory_limit" {
  description = "PostgreSQL container memory limit (e.g., '2g')"
  type        = string
  default     = "2g"
}

variable "postgres_cpu_limit" {
  description = "PostgreSQL container CPU limit (e.g., '1.0')"
  type        = string
  default     = "1.0"
}

# =============================================================================
# Redis Configuration
# =============================================================================

variable "redis_password" {
  description = "Redis password (optional but recommended)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "redis_max_memory" {
  description = "Redis maximum memory (e.g., '4gb')"
  type        = string
  default     = "1gb"
}

variable "redis_enable_persistence" {
  description = "Enable Redis AOF persistence"
  type        = bool
  default     = true
}

variable "redis_enable_replica" {
  description = "Enable Redis replica for high availability"
  type        = bool
  default     = false
}

variable "redis_memory_limit" {
  description = "Redis container memory limit"
  type        = string
  default     = "1g"
}

variable "redis_cpu_limit" {
  description = "Redis container CPU limit"
  type        = string
  default     = "0.5"
}

# =============================================================================
# RabbitMQ Configuration
# =============================================================================

variable "rabbitmq_user" {
  description = "RabbitMQ admin username"
  type        = string
  default     = "cognive"
}

variable "rabbitmq_password" {
  description = "RabbitMQ admin password"
  type        = string
  sensitive   = true
}

variable "rabbitmq_memory_limit" {
  description = "RabbitMQ container memory limit"
  type        = string
  default     = "1g"
}

variable "rabbitmq_cpu_limit" {
  description = "RabbitMQ container CPU limit"
  type        = string
  default     = "0.5"
}

variable "rabbitmq_enable_management_ui" {
  description = "Enable RabbitMQ management UI"
  type        = bool
  default     = true
}

variable "rabbitmq_management_port" {
  description = "RabbitMQ management UI port"
  type        = number
  default     = 15672
}

# =============================================================================
# MinIO Configuration
# =============================================================================

variable "minio_root_user" {
  description = "MinIO root user"
  type        = string
  default     = "cognive"
}

variable "minio_root_password" {
  description = "MinIO root password (min 8 characters)"
  type        = string
  sensitive   = true
}

variable "minio_api_port" {
  description = "MinIO API port"
  type        = number
  default     = 9000
}

variable "minio_console_port" {
  description = "MinIO console port"
  type        = number
  default     = 9001
}

variable "minio_memory_limit" {
  description = "MinIO container memory limit"
  type        = string
  default     = "512m"
}

variable "minio_cpu_limit" {
  description = "MinIO container CPU limit"
  type        = string
  default     = "0.5"
}

variable "minio_default_buckets" {
  description = "Default buckets to create in MinIO"
  type        = list(string)
  default     = ["cognive-logs", "cognive-artifacts", "cognive-backups"]
}

# =============================================================================
# Monitoring Configuration
# =============================================================================

variable "enable_monitoring" {
  description = "Enable monitoring stack (Prometheus + Grafana)"
  type        = bool
  default     = true
}

variable "prometheus_retention_days" {
  description = "Prometheus data retention in days"
  type        = number
  default     = 15
}

variable "prometheus_port" {
  description = "Prometheus web UI port"
  type        = number
  default     = 9090
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

variable "grafana_port" {
  description = "Grafana web UI port"
  type        = number
  default     = 3000
}

variable "enable_loki" {
  description = "Enable Loki for log aggregation"
  type        = bool
  default     = false
}

variable "loki_port" {
  description = "Loki API port"
  type        = number
  default     = 3100
}

