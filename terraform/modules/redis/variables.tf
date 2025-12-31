# =============================================================================
# Redis Module Variables
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

# Redis Configuration
variable "redis_password" {
  description = "Redis password (optional but recommended)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "max_memory" {
  description = "Redis maximum memory (e.g., '1gb', '4gb')"
  type        = string
  default     = "1gb"
}

variable "eviction_policy" {
  description = "Redis eviction policy when max memory is reached"
  type        = string
  default     = "allkeys-lru"

  validation {
    condition = contains([
      "noeviction",
      "allkeys-lru",
      "allkeys-lfu",
      "volatile-lru",
      "volatile-lfu",
      "allkeys-random",
      "volatile-random",
      "volatile-ttl"
    ], var.eviction_policy)
    error_message = "Invalid eviction policy."
  }
}

# Persistence Configuration
variable "enable_persistence" {
  description = "Enable AOF persistence"
  type        = bool
  default     = true
}

# High Availability
variable "enable_replica" {
  description = "Enable Redis replica for high availability"
  type        = bool
  default     = false
}

# Storage Configuration
variable "data_volume_name" {
  description = "Name for the Redis data volume"
  type        = string
}

# Port Configuration
variable "external_port" {
  description = "External port for Redis"
  type        = number
  default     = 6379
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

