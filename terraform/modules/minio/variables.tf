# =============================================================================
# MinIO Module Variables
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

# MinIO Configuration
variable "root_user" {
  description = "MinIO root user (access key)"
  type        = string
}

variable "root_password" {
  description = "MinIO root password (secret key, min 8 characters)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.root_password) >= 8
    error_message = "MinIO root password must be at least 8 characters."
  }
}

# Port Configuration
variable "api_port" {
  description = "External API port (S3-compatible)"
  type        = number
  default     = 9000
}

variable "console_port" {
  description = "External console port"
  type        = number
  default     = 9001
}

# Storage Configuration
variable "data_volume_name" {
  description = "Name for the MinIO data volume"
  type        = string
}

# Bucket Configuration
variable "default_buckets" {
  description = "List of default buckets to create"
  type        = list(string)
  default     = []
}

# Resource Limits
variable "memory_limit" {
  description = "Container memory limit (e.g., '512m')"
  type        = string
  default     = "512m"
}

variable "cpu_limit" {
  description = "Container CPU limit (e.g., '0.5')"
  type        = string
  default     = "0.5"
}

# Tags
variable "common_tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
  default     = {}
}

