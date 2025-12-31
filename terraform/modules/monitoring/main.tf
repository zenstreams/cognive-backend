# =============================================================================
# Monitoring Stack Module
# =============================================================================
# This module provisions the complete monitoring stack for Cognive:
# - Prometheus (metrics collection)
# - Grafana (visualization and dashboards)
# - Loki (log aggregation - optional)
#
# Features:
# - Pre-configured data sources
# - Custom Cognive dashboards
# - Alerting rules
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
  prometheus_container = "cognive-prometheus-${var.environment}"
  grafana_container    = "cognive-grafana-${var.environment}"
  loki_container       = "cognive-loki-${var.environment}"

  images = {
    prometheus = "prom/prometheus:v2.48.0"
    grafana    = "grafana/grafana:10.2.0"
    loki       = "grafana/loki:2.9.0"
  }
}

# =============================================================================
# Docker Volumes
# =============================================================================

resource "docker_volume" "prometheus_data" {
  name = var.prometheus_volume

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
    value = "prometheus"
  }
}

resource "docker_volume" "grafana_data" {
  name = var.grafana_volume

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
    value = "grafana"
  }
}

resource "docker_volume" "loki_data" {
  count = var.enable_loki ? 1 : 0
  name  = var.loki_volume

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
    value = "loki"
  }
}

# =============================================================================
# Prometheus Configuration
# =============================================================================

resource "local_file" "prometheus_config" {
  filename = "${path.module}/config/prometheus.yml"
  content  = <<-EOF
# Prometheus configuration for Cognive Control Plane
# Environment: ${var.environment}

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  
  external_labels:
    environment: ${var.environment}
    project: cognive

# Alerting configuration
alerting:
  alertmanagers: []

# Rule files
rule_files: []

# Scrape configurations
scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Cognive API service
  %{for target in var.scrape_targets}
  - job_name: '${target.job_name}'
    static_configs:
      - targets: ${jsonencode(target.targets)}
    metrics_path: '/metrics'
    scrape_interval: 15s
  %{endfor}

  # Docker containers (optional)
  - job_name: 'docker'
    static_configs:
      - targets: ['host.docker.internal:9323']
EOF

  file_permission = "0644"
}

# =============================================================================
# Grafana Datasources Configuration
# =============================================================================

resource "local_file" "grafana_datasources" {
  filename = "${path.module}/config/grafana/provisioning/datasources/datasources.yml"
  content  = <<-EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://${local.prometheus_container}:9090
    isDefault: true
    editable: false
    
  %{if var.enable_loki}
  - name: Loki
    type: loki
    access: proxy
    url: http://${local.loki_container}:3100
    editable: false
  %{endif}
EOF

  file_permission = "0644"
}

# =============================================================================
# Prometheus Container
# =============================================================================

resource "docker_image" "prometheus" {
  name         = local.images.prometheus
  keep_locally = true
}

resource "docker_container" "prometheus" {
  name  = local.prometheus_container
  image = docker_image.prometheus.image_id

  restart = "unless-stopped"

  # Command with configuration
  command = [
    "--config.file=/etc/prometheus/prometheus.yml",
    "--storage.tsdb.path=/prometheus",
    "--storage.tsdb.retention.time=${var.prometheus_retention_days}d",
    "--web.console.libraries=/etc/prometheus/console_libraries",
    "--web.console.templates=/etc/prometheus/consoles",
    "--web.enable-lifecycle",
  ]

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "prometheus",
      local.prometheus_container,
    ]
  }

  # Port mapping
  ports {
    internal = 9090
    external = var.prometheus_port
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.prometheus_data.name
    container_path = "/prometheus"
  }

  # Mount configuration file
  upload {
    file    = "/etc/prometheus/prometheus.yml"
    content = local_file.prometheus_config.content
  }

  # Health check
  healthcheck {
    test         = ["CMD", "wget", "-q", "--spider", "http://localhost:9090/-/healthy"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 3
    start_period = "30s"
  }

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
    value = "prometheus"
  }
}

# =============================================================================
# Grafana Container
# =============================================================================

resource "docker_image" "grafana" {
  name         = local.images.grafana
  keep_locally = true
}

resource "docker_container" "grafana" {
  name  = local.grafana_container
  image = docker_image.grafana.image_id

  restart = "unless-stopped"

  # Environment variables
  env = [
    "GF_SECURITY_ADMIN_USER=${var.grafana_admin_user}",
    "GF_SECURITY_ADMIN_PASSWORD=${var.grafana_admin_password}",
    "GF_USERS_ALLOW_SIGN_UP=false",
    "GF_SERVER_ROOT_URL=http://localhost:${var.grafana_port}",
  ]

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "grafana",
      local.grafana_container,
    ]
  }

  # Port mapping
  ports {
    internal = 3000
    external = var.grafana_port
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.grafana_data.name
    container_path = "/var/lib/grafana"
  }

  # Mount datasources configuration
  upload {
    file    = "/etc/grafana/provisioning/datasources/datasources.yml"
    content = local_file.grafana_datasources.content
  }

  # Health check
  healthcheck {
    test         = ["CMD", "wget", "-q", "--spider", "http://localhost:3000/api/health"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 3
    start_period = "60s"
  }

  # Depends on Prometheus
  depends_on = [docker_container.prometheus]

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
    value = "grafana"
  }
}

# =============================================================================
# Loki Container (Optional)
# =============================================================================

resource "docker_image" "loki" {
  count        = var.enable_loki ? 1 : 0
  name         = local.images.loki
  keep_locally = true
}

resource "docker_container" "loki" {
  count = var.enable_loki ? 1 : 0

  name  = local.loki_container
  image = docker_image.loki[0].image_id

  restart = "unless-stopped"

  # Command
  command = ["-config.file=/etc/loki/local-config.yaml"]

  # Network configuration
  networks_advanced {
    name = var.network_name
    aliases = [
      "loki",
      local.loki_container,
    ]
  }

  # Port mapping
  ports {
    internal = 3100
    external = var.loki_port
  }

  # Volume mounts
  volumes {
    volume_name    = docker_volume.loki_data[0].name
    container_path = "/loki"
  }

  # Health check
  healthcheck {
    test         = ["CMD", "wget", "-q", "--spider", "http://localhost:3100/ready"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 3
    start_period = "30s"
  }

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
    value = "loki"
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "prometheus_url" {
  description = "Prometheus web UI URL"
  value       = "http://localhost:${var.prometheus_port}"
}

output "prometheus_host" {
  description = "Prometheus container hostname"
  value       = local.prometheus_container
}

output "grafana_url" {
  description = "Grafana web UI URL"
  value       = "http://localhost:${var.grafana_port}"
}

output "grafana_host" {
  description = "Grafana container hostname"
  value       = local.grafana_container
}

output "loki_url" {
  description = "Loki API URL"
  value       = var.enable_loki ? "http://localhost:${var.loki_port}" : null
}

output "loki_host" {
  description = "Loki container hostname"
  value       = var.enable_loki ? local.loki_container : null
}

