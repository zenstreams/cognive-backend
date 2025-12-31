# =============================================================================
# RabbitMQ Module Variables
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

# RabbitMQ Configuration
variable "rabbitmq_user" {
  description = "RabbitMQ admin username"
  type        = string
}

variable "rabbitmq_password" {
  description = "RabbitMQ admin password"
  type        = string
  sensitive   = true
}

# Port Configuration
variable "amqp_port" {
  description = "External AMQP port"
  type        = number
  default     = 5672
}

variable "enable_management_ui" {
  description = "Enable RabbitMQ management UI"
  type        = bool
  default     = true
}

variable "management_port" {
  description = "External management UI port"
  type        = number
  default     = 15672
}

# Storage Configuration
variable "data_volume_name" {
  description = "Name for the RabbitMQ data volume"
  type        = string
}

# Resource Limits
variable "memory_limit" {
  description = "Container memory limit (e.g., '1g')"
  type        = string
  default     = "1g"
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

