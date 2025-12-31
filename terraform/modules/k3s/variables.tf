# =============================================================================
# k3s Module Variables
# =============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "k3s_version" {
  description = "k3s version to install"
  type        = string
  default     = "v1.28.4+k3s2"
}

variable "tls_san" {
  description = "Additional TLS SAN for the Kubernetes API (e.g., public IP or domain)"
  type        = string
  default     = ""
}

variable "disable_local_storage" {
  description = "Disable built-in local-path storage provisioner"
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
  default     = {}
}

