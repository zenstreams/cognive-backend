# =============================================================================
# Monitoring Stack Module Variables
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

# Prometheus Configuration
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

variable "prometheus_volume" {
  description = "Prometheus data volume name"
  type        = string
}

variable "scrape_targets" {
  description = "List of Prometheus scrape targets"
  type = list(object({
    job_name = string
    targets  = list(string)
  }))
  default = []
}

# Grafana Configuration
variable "grafana_admin_user" {
  description = "Grafana admin username"
  type        = string
  default     = "admin"
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
}

variable "grafana_port" {
  description = "Grafana web UI port"
  type        = number
  default     = 3000
}

variable "grafana_volume" {
  description = "Grafana data volume name"
  type        = string
}

# Loki Configuration
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

variable "loki_volume" {
  description = "Loki data volume name"
  type        = string
}

# Tags
variable "common_tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
  default     = {}
}

