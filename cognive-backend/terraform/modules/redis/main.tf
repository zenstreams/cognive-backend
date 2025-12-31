# =============================================================================
# Redis Module
# =============================================================================
# This module provisions Redis for the Cognive Control Plane cache layer.
#
# Features:
# - Redis 7 with Alpine base image
# - Optional password authentication
# - AOF persistence for durability
# - Configurable memory limits and eviction policies
# - Optional replica for high availability
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
  container_name = "cognive-redis-${var.environment}"
  replica_name   = "cognive-redis-replica-${var.environment}"
  image          = "redis:7-alpine"

  # Parse memory limit with m or g suffix
  memory_bytes = var.memory_limit != "" ? (
    can(regex("g$", lower(var.memory_limit))) ?
    parseint(replace(lower(var.memory_limit), "g", ""), 10) * 1024 * 1024 * 1024 :
    can(regex("m$", lower(var.memory_limit))) ?
    parseint(replace(lower(var.memory_limit), "m", ""), 10) * 1024 * 1024 :
    null
  ) : null

  # Build Redis command with configuration
  redis_command = compact([
    "redis-server",
    var.enable_persistence ? "--appendonly yes" : "--appendonly no",
    "--maxmemory ${var.max_memory}",
    "--maxmemory-policy ${var.eviction_policy}",
    var.redis_password != "" ? "--requirepass ${var.redis_password}" : "",
  ])

  # Replica command (connects to master)
  replica_command = compact([
    "redis-server",
    "--appendonly yes",
    "--maxmemory ${var.max_memory}",
    "--maxmemory-policy ${var.eviction_policy}",
    "--replicaof ${local.container_name} 6379",
    var.redis_password != "" ? "--requirepass ${var.redis_password}" : "",
    var.redis_password != "" ? "--masterauth ${var.redis_password}" : "",
  ])
}

# =============================================================================
# Docker Volume
# =============================================================================

resource "docker_volume" "redis_data" {
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
    value = "redis"
  }
}

resource "docker_volume" "redis_replica_data" {
  count = var.enable_replica ? 1 : 0
  name  = "${var.data_volume_name}-replica"

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
    value = "redis-replica"
  }
}

# =============================================================================
# Redis Primary Container
# =============================================================================

resource "docker_image" "redis" {
  name         = local.image
  keep_locally = true
}

resource "docker_container" "redis" {
  name  = local.container_name
  image = docker_image.redis.image_id

  restart = "unless-stopped"

  # Command with configuration
  command = local.redis_command

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "redis",
      "redis-master",
      local.container_name,
    ]
  }

  # Port mapping
  ports {
    internal = 6379
    external = var.external_port
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.redis_data.name
    container_path = "/data"
  }

  # Health check
  healthcheck {
    test         = ["CMD", "redis-cli", "ping"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 5
    start_period = "10s"
  }

  # Resource limits
  memory = local.memory_bytes

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
    value = "redis-master"
  }
}

# =============================================================================
# Redis Replica Container (Optional)
# =============================================================================

resource "docker_container" "redis_replica" {
  count = var.enable_replica ? 1 : 0

  name  = local.replica_name
  image = docker_image.redis.image_id

  restart = "unless-stopped"

  # Command with replica configuration
  command = local.replica_command

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "redis-replica",
      local.replica_name,
    ]
  }

  # Port mapping (offset from master)
  ports {
    internal = 6379
    external = var.external_port + 1
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.redis_replica_data[0].name
    container_path = "/data"
  }

  # Health check
  healthcheck {
    test         = ["CMD", "redis-cli", "ping"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 5
    start_period = "10s"
  }

  # Resource limits
  memory = local.memory_bytes

  # Depends on master
  depends_on = [docker_container.redis]

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
    value = "redis-replica"
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "host" {
  description = "Redis container hostname"
  value       = local.container_name
}

output "port" {
  description = "Redis external port"
  value       = var.external_port
}

output "replica_host" {
  description = "Redis replica hostname (if enabled)"
  value       = var.enable_replica ? local.replica_name : null
}

output "replica_port" {
  description = "Redis replica port (if enabled)"
  value       = var.enable_replica ? var.external_port + 1 : null
}

output "connection_url" {
  description = "Redis connection URL"
  value       = var.redis_password != "" ? "redis://:${var.redis_password}@${local.container_name}:6379" : "redis://${local.container_name}:6379"
  sensitive   = true
}

output "volume_name" {
  description = "Redis data volume name"
  value       = docker_volume.redis_data.name
}

