# =============================================================================
# RabbitMQ Module
# =============================================================================
# This module provisions RabbitMQ for the Cognive Control Plane message queue.
#
# Features:
# - RabbitMQ 3 with Management UI
# - Persistent storage for durability
# - Configurable users and permissions
# - Health checks and monitoring
# =============================================================================

terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

# =============================================================================
# Local Variables
# =============================================================================

locals {
  container_name = "cognive-rabbitmq-${var.environment}"
  image          = "rabbitmq:3-management"
}

# =============================================================================
# Docker Volume
# =============================================================================

resource "docker_volume" "rabbitmq_data" {
  name = var.data_volume_name

  labels {
    label = "project"
    value = "cognive"
  }

  labels {
    label = "environment"
    value = var.environment
  }

  labels {
    label = "component"
    value = "rabbitmq"
  }
}

# =============================================================================
# RabbitMQ Container
# =============================================================================

resource "docker_image" "rabbitmq" {
  name         = local.image
  keep_locally = true
}

resource "docker_container" "rabbitmq" {
  name  = local.container_name
  image = docker_image.rabbitmq.image_id

  restart = "unless-stopped"

  # Environment variables
  env = [
    "RABBITMQ_DEFAULT_USER=${var.rabbitmq_user}",
    "RABBITMQ_DEFAULT_PASS=${var.rabbitmq_password}",
    "RABBITMQ_VM_MEMORY_HIGH_WATERMARK=0.8",
  ]

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "rabbitmq",
      local.container_name,
    ]
  }

  # Port mappings
  # AMQP port
  ports {
    internal = 5672
    external = var.amqp_port
  }

  # Management UI port (conditional)
  dynamic "ports" {
    for_each = var.enable_management_ui ? [1] : []
    content {
      internal = 15672
      external = var.management_port
    }
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.rabbitmq_data.name
    container_path = "/var/lib/rabbitmq"
  }

  # Health check
  healthcheck {
    test         = ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 5
    start_period = "60s"
  }

  # Resource limits - parse memory with m or g suffix
  memory = var.memory_limit != "" ? (
    can(regex("g$", var.memory_limit)) ?
    parseint(replace(var.memory_limit, "g", ""), 10) * 1024 * 1024 * 1024 :
    can(regex("m$", var.memory_limit)) ?
    parseint(replace(var.memory_limit, "m", ""), 10) * 1024 * 1024 :
    null
  ) : null

  # Labels
  labels {
    label = "project"
    value = "cognive"
  }

  labels {
    label = "environment"
    value = var.environment
  }

  labels {
    label = "component"
    value = "rabbitmq"
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "host" {
  description = "RabbitMQ container hostname"
  value       = local.container_name
}

output "port" {
  description = "RabbitMQ AMQP port"
  value       = var.amqp_port
}

output "management_port" {
  description = "RabbitMQ management UI port"
  value       = var.enable_management_ui ? var.management_port : null
}

output "amqp_url" {
  description = "RabbitMQ AMQP connection URL"
  value       = "amqp://${var.rabbitmq_user}:${var.rabbitmq_password}@${local.container_name}:5672/"
  sensitive   = true
}

output "management_url" {
  description = "RabbitMQ management UI URL"
  value       = var.enable_management_ui ? "http://localhost:${var.management_port}" : null
}

output "volume_name" {
  description = "RabbitMQ data volume name"
  value       = docker_volume.rabbitmq_data.name
}

