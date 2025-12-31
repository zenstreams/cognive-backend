# Cognive Control Plane - Terraform Infrastructure

This directory contains Terraform Infrastructure as Code (IaC) for provisioning and managing the Cognive Control Plane infrastructure.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Modules](#modules)
- [Environments](#environments)
- [State Management](#state-management)
- [Deployment Guides](#deployment-guides)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)

---

## Overview

### What This Provides

Terraform configurations for deploying the complete Cognive Control Plane stack:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Database** | PostgreSQL 15 + TimescaleDB | Primary database with time-series support |
| **Cache** | Redis 7 | Session management, caching, rate limiting |
| **Message Queue** | RabbitMQ 3 | Async event processing, task queues |
| **Object Storage** | MinIO | S3-compatible storage for logs/artifacts |
| **Monitoring** | Prometheus + Grafana | Metrics, dashboards, alerting |
| **Logging** | Loki (optional) | Centralized log aggregation |
| **Kubernetes** | k3s | Lightweight container orchestration |

### Deployment Options

| Option | Cost | Best For |
|--------|------|----------|
| **Self-Hosted (Docker)** | $40-50/mo (VPS) | Development, small teams |
| **Oracle Cloud Always Free** | $0/mo | MVPs, side projects, cost-conscious |
| **AWS** | $300+/mo | Enterprise, managed services |

---

## Prerequisites

### Required Software

```bash
# Install Terraform (macOS)
brew install terraform

# Install Terraform (Linux)
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verify installation
terraform version
# Terraform v1.6.x
```

### Required for Docker Deployments

```bash
# Docker and Docker Compose must be installed
docker --version
docker-compose --version
```

### Optional Tools

```bash
# For k3s deployments
curl -sfL https://get.k3s.io | sh -

# For Oracle Cloud
brew install oci-cli  # macOS

# For AWS
brew install awscli   # macOS
```

---

## Quick Start

### 1. Development Environment (Local Docker)

```bash
# Navigate to terraform directory
cd cognive-backend/terraform

# Go to dev environment
cd environments/dev

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply

# When prompted, type 'yes' to confirm
```

### 2. Verify Deployment

After `terraform apply` completes:

```bash
# Check running containers
docker ps

# Test PostgreSQL
psql postgresql://cognive:your_password@localhost:5432/cognive

# Test Redis
redis-cli ping

# Open RabbitMQ UI
open http://localhost:15672

# Open MinIO Console
open http://localhost:9003

# Open Grafana
open http://localhost:3000
```

### 3. Destroy Infrastructure

```bash
# Remove all resources
terraform destroy

# Confirm with 'yes'
```

---

## Project Structure

```
terraform/
├── main.tf                 # Root module - orchestrates all components
├── variables.tf            # Input variable definitions
├── versions.tf             # Terraform and provider versions
├── .gitignore              # Ignore state files and secrets
│
├── modules/                # Reusable infrastructure modules
│   ├── k3s/               # Lightweight Kubernetes cluster
│   │   ├── main.tf
│   │   └── variables.tf
│   ├── postgres/          # PostgreSQL + TimescaleDB
│   │   ├── main.tf
│   │   └── variables.tf
│   ├── redis/             # Redis cache
│   │   ├── main.tf
│   │   └── variables.tf
│   ├── rabbitmq/          # RabbitMQ message queue
│   │   ├── main.tf
│   │   └── variables.tf
│   ├── minio/             # S3-compatible object storage
│   │   ├── main.tf
│   │   └── variables.tf
│   └── monitoring/        # Prometheus + Grafana + Loki
│       ├── main.tf
│       └── variables.tf
│
├── environments/          # Environment-specific configurations
│   ├── dev/               # Development (local Docker)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars.example
│   ├── staging/           # Staging (production-like)
│   │   ├── main.tf
│   │   └── variables.tf
│   └── production/        # Production (full HA)
│       ├── main.tf
│       └── variables.tf
│
└── backends/              # State backend configurations
    ├── local.tf           # Local state (dev)
    ├── s3.tf.example      # S3/MinIO state (staging/prod)
    └── oracle.tf.example  # Oracle Cloud state
```

---

## Modules

### PostgreSQL Module (`modules/postgres`)

Provisions PostgreSQL 15 with TimescaleDB extension.

**Features:**
- TimescaleDB for time-series data
- Streaming replication (configurable replicas)
- WAL archiving for point-in-time recovery
- Health checks and auto-restart

**Outputs:**
- `primary_host` - Primary database hostname
- `connection_string` - Full connection string (sensitive)
- `replica_hosts` - List of replica hostnames

### Redis Module (`modules/redis`)

Provisions Redis 7 with optional replica.

**Features:**
- AOF persistence for durability
- Configurable memory limits and eviction
- Optional replica for HA
- Password authentication

**Outputs:**
- `host` - Redis hostname
- `connection_url` - Full connection URL

### RabbitMQ Module (`modules/rabbitmq`)

Provisions RabbitMQ 3 with management UI.

**Features:**
- Management UI for monitoring
- Persistent storage
- Health checks

**Outputs:**
- `amqp_url` - AMQP connection URL
- `management_url` - Management UI URL

### MinIO Module (`modules/minio`)

Provisions MinIO for S3-compatible object storage.

**Features:**
- S3-compatible API
- Web console
- Automatic bucket creation
- Persistent storage

**Outputs:**
- `endpoint` - S3 API endpoint
- `console_url` - Web console URL

### Monitoring Module (`modules/monitoring`)

Provisions complete monitoring stack.

**Components:**
- Prometheus - Metrics collection
- Grafana - Visualization and dashboards
- Loki (optional) - Log aggregation

**Outputs:**
- `prometheus_url` - Prometheus UI
- `grafana_url` - Grafana UI

### k3s Module (`modules/k3s`)

Generates installation scripts for k3s Kubernetes cluster.

**Features:**
- Server installation script
- Agent (worker) installation script
- Namespace manifests

**Outputs:**
- `install_script_path` - Path to server install script
- `k3s_token` - Cluster join token

---

## Environments

### Development (`environments/dev`)

- Single-node deployment
- No replicas
- Monitoring enabled
- Lower resource limits

```bash
cd environments/dev
terraform init && terraform apply
```

### Staging (`environments/staging`)

- Production-like configuration
- 1 PostgreSQL replica
- Redis replica enabled
- Full monitoring stack

```bash
cd environments/staging
terraform init && terraform apply
```

### Production (`environments/production`)

- Full HA configuration
- 2 PostgreSQL replicas
- Redis replica
- Extended monitoring retention
- Strong password requirements

```bash
cd environments/production
terraform init && terraform apply
```

---

## State Management

### Local State (Development)

Default for development. State stored in `terraform.tfstate`.

```hcl
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
```

### S3/MinIO State (Staging/Production)

Recommended for team environments.

```bash
# Set credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# For MinIO
export AWS_S3_ENDPOINT="http://minio.example.com:9000"
```

See `backends/s3.tf.example` for configuration.

### Oracle Cloud State

Use Oracle Object Storage (S3-compatible).

See `backends/oracle.tf.example` for configuration.

---

## Deployment Guides

### Deploy to VPS (Hetzner, DigitalOcean, Linode)

1. **Provision VPS** (recommended specs):
   - CPU: 4 vCPU
   - RAM: 8GB
   - Storage: 160GB SSD
   - Cost: ~$40-50/mo

2. **Install Docker on VPS**:
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

3. **Clone repository and deploy**:
```bash
git clone https://github.com/your-org/cognive-backend.git
cd cognive-backend/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with secure passwords
terraform init && terraform apply
```

### Deploy to Oracle Cloud Always Free

1. **Create Oracle Cloud Account** (free):
   - https://cloud.oracle.com/

2. **Create ARM Instance**:
   - Shape: `VM.Standard.A1.Flex`
   - Resources: 4 OCPU, 24GB RAM (all free!)

3. **Install Docker and deploy** (same as VPS)

4. **Configure firewall**:
```bash
sudo firewall-cmd --add-port=8000/tcp --permanent  # API
sudo firewall-cmd --add-port=443/tcp --permanent   # HTTPS
sudo firewall-cmd --reload
```

### Deploy to Kubernetes (k3s)

1. **Install k3s**:
```bash
# Run the generated script
./terraform/modules/k3s/generated/install-k3s-server.sh
```

2. **Deploy Cognive**:
```bash
# Apply namespace
kubectl apply -f terraform/modules/k3s/generated/namespace.yaml

# Deploy with Helm or kubectl
# (Kubernetes manifests in a separate directory)
```

---

## Configuration Reference

### Common Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `environment` | Environment name (dev/staging/production) | `dev` |
| `docker_host` | Docker daemon socket | `unix:///var/run/docker.sock` |

### PostgreSQL Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `postgres_user` | Database admin username | `cognive` |
| `postgres_password` | Database admin password | *required* |
| `postgres_db` | Database name | `cognive` |
| `enable_postgres_replicas` | Enable read replicas | `false` |
| `postgres_replica_count` | Number of replicas | `2` |
| `postgres_memory_limit` | Container memory limit | `2g` |

### Redis Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `redis_password` | Redis password | `` (optional) |
| `redis_max_memory` | Maximum memory | `1gb` |
| `redis_enable_persistence` | Enable AOF persistence | `true` |
| `redis_enable_replica` | Enable replica | `false` |

### Monitoring Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `enable_monitoring` | Enable monitoring stack | `true` |
| `prometheus_retention_days` | Metrics retention | `15` |
| `grafana_admin_user` | Grafana admin username | `admin` |
| `grafana_admin_password` | Grafana admin password | *required* |
| `enable_loki` | Enable Loki logging | `false` |

---

## Troubleshooting

### Common Issues

#### "Provider not found" error

```bash
# Re-initialize Terraform
terraform init -upgrade
```

#### Docker connection refused

```bash
# Verify Docker is running
sudo systemctl status docker

# Check Docker socket permissions
sudo chmod 666 /var/run/docker.sock
```

#### PostgreSQL container not starting

```bash
# Check logs
docker logs cognive-postgres-dev

# Common fix: remove corrupted volume
docker volume rm cognive-postgres-data-dev
terraform apply
```

#### State lock error

```bash
# If using local state and interrupted
rm .terraform.lock.hcl
terraform init
```

### Getting Help

- Review logs: `docker logs <container-name>`
- Check state: `terraform show`
- Validate config: `terraform validate`
- Format code: `terraform fmt -recursive`

---

## Security Best Practices

1. **Never commit secrets** - Use `.tfvars` files (gitignored)
2. **Use strong passwords** - Production requires 16+ characters
3. **Enable TLS** - Configure SSL/TLS for all external endpoints
4. **Limit network access** - Use firewalls to restrict port access
5. **Rotate credentials** - Regularly update passwords
6. **Use secrets manager** - HashiCorp Vault or cloud provider

---

## Related Documentation

- [CONTROL_PLANE_ARCHITECTURE.md](../../cognive-docs/CONTROL_PLANE_ARCHITECTURE.md) - Full architecture documentation
- [TECH_STACK.md](../../cognive-docs/TECH_STACK.md) - Technology stack details
- [PRODUCT_ROADMAP.md](../../cognive-docs/PRODUCT_ROADMAP.md) - Product roadmap

---

## Contributing

1. Format code: `terraform fmt -recursive`
2. Validate: `terraform validate`
3. Test in dev environment before staging/production

---

## License

Internal use only - Cognive Project

---

*Generated for SCRUM-81: Set up Terraform infrastructure as code*

