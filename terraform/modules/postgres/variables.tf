# =============================================================================
# PostgreSQL Module Variables
# =============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "network_name" {
  description = "Docker network name to attach containers"
  type        = string
}

variable "network_id" {
  description = "Docker network ID"
  type        = string
}

# Database Configuration
variable "postgres_user" {
  description = "PostgreSQL admin username"
  type        = string
}

variable "postgres_password" {
  description = "PostgreSQL admin password"
  type        = string
  sensitive   = true
}

variable "postgres_db" {
  description = "PostgreSQL database name"
  type        = string
}

# Replication Configuration
variable "enable_replicas" {
  description = "Enable PostgreSQL read replicas"
  type        = bool
  default     = false
}

variable "replica_count" {
  description = "Number of read replicas"
  type        = number
  default     = 2
}

variable "replication_password" {
  description = "Password for replication user (auto-generated if empty)"
  type        = string
  sensitive   = true
  default     = ""
}

# Storage Configuration
variable "data_volume_name" {
  description = "Name for the PostgreSQL data volume"
  type        = string
}

# Port Configuration
variable "primary_external_port" {
  description = "External port for PostgreSQL primary"
  type        = number
  default     = 5432
}

# Resource Limits
variable "memory_limit" {
  description = "Container memory limit (e.g., '2g')"
  type        = string
  default     = "2g"
}

variable "cpu_limit" {
  description = "Container CPU limit (e.g., '1.0')"
  type        = string
  default     = "1.0"
}

# Tags
variable "common_tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
  default     = {}
}

