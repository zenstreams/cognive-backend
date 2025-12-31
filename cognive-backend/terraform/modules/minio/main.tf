# =============================================================================
# MinIO Module
# =============================================================================
# This module provisions MinIO for S3-compatible object storage.
#
# Features:
# - S3-compatible API
# - Web console for management
# - Automatic bucket creation
# - Persistent storage
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
  container_name = "cognive-minio-${var.environment}"
  image          = "minio/minio:latest"

  # Parse memory limit with m or g suffix
  memory_bytes = var.memory_limit != "" ? (
    can(regex("g$", lower(var.memory_limit))) ?
    parseint(replace(lower(var.memory_limit), "g", ""), 10) * 1024 * 1024 * 1024 :
    can(regex("m$", lower(var.memory_limit))) ?
    parseint(replace(lower(var.memory_limit), "m", ""), 10) * 1024 * 1024 :
    null
  ) : null
}

# =============================================================================
# Docker Volume
# =============================================================================

resource "docker_volume" "minio_data" {
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
    value = "minio"
  }
}

# =============================================================================
# MinIO Container
# =============================================================================

resource "docker_image" "minio" {
  name         = local.image
  keep_locally = true
}

resource "docker_container" "minio" {
  name  = local.container_name
  image = docker_image.minio.image_id

  restart = "unless-stopped"

  # Environment variables
  env = [
    "MINIO_ROOT_USER=${var.root_user}",
    "MINIO_ROOT_PASSWORD=${var.root_password}",
  ]

  # Command to start server with console
  command = ["server", "/data", "--console-address", ":9001"]

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "minio",
      "s3",
      local.container_name,
    ]
  }

  # Port mappings
  # API port
  ports {
    internal = 9000
    external = var.api_port
  }

  # Console port
  ports {
    internal = 9001
    external = var.console_port
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.minio_data.name
    container_path = "/data"
  }

  # Health check
  healthcheck {
    test         = ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 3
    start_period = "30s"
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
    value = "minio"
  }
}

# =============================================================================
# Create Default Buckets
# =============================================================================

resource "null_resource" "create_buckets" {
  count = length(var.default_buckets) > 0 ? 1 : 0

  triggers = {
    buckets         = join(",", var.default_buckets)
    minio_container = docker_container.minio.id
  }

  provisioner "local-exec" {
    command = <<-EOF
      set -euo pipefail

      # Avoid embedding raw credentials directly in shell (handles special chars safely)
      ROOT_USER_B64='${base64encode(var.root_user)}'
      ROOT_PASS_B64='${base64encode(var.root_password)}'
      root_user="$(printf '%s' "$ROOT_USER_B64" | base64 --decode)"
      root_pass="$(printf '%s' "$ROOT_PASS_B64" | base64 --decode)"

      network='${var.network_name}'
      endpoint="http://${local.container_name}:9000"
      alias_name="cognive"

      echo "Waiting for MinIO to be ready at $endpoint (network: $network)..."
      for i in $(seq 1 60); do
        if docker run --rm --network "$network" minio/mc:latest alias set "$alias_name" "$endpoint" "$root_user" "$root_pass" >/dev/null 2>&1; then
          break
        fi
        sleep 2
      done

      %{for bucket in var.default_buckets}
      echo "Creating bucket: ${bucket}"
      docker run --rm --network "$network" minio/mc:latest mb --ignore-existing "$${alias_name}/${bucket}" >/dev/null
      %{endfor}

      echo "Buckets created successfully."
    EOF
  }

  depends_on = [docker_container.minio]
}

# =============================================================================
# Outputs
# =============================================================================

output "host" {
  description = "MinIO container hostname"
  value       = local.container_name
}

output "endpoint" {
  description = "MinIO S3 endpoint"
  value       = "http://${local.container_name}:9000"
}

output "api_port" {
  description = "MinIO API port"
  value       = var.api_port
}

output "console_port" {
  description = "MinIO console port"
  value       = var.console_port
}

output "console_url" {
  description = "MinIO console URL"
  value       = "http://localhost:${var.console_port}"
}

output "access_key" {
  description = "MinIO access key (root user)"
  value       = var.root_user
  sensitive   = true
}

output "secret_key" {
  description = "MinIO secret key (root password)"
  value       = var.root_password
  sensitive   = true
}

output "volume_name" {
  description = "MinIO data volume name"
  value       = docker_volume.minio_data.name
}

