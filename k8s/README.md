# Cognive Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the Cognive Control Plane on k3s/MicroK8s or any Kubernetes cluster.

## 📁 Directory Structure

```
k8s/
├── README.md                    # This file
├── namespace.yaml               # Cognive namespace
├── rbac/                        # RBAC configurations
│   ├── service-accounts.yaml
│   ├── roles.yaml
│   └── role-bindings.yaml
├── deployments/                 # Application deployments
│   ├── api-deployment.yaml
│   ├── celery-deployment.yaml
│   └── flower-deployment.yaml
├── services/                    # Kubernetes services
│   ├── api-service.yaml
│   ├── postgres-service.yaml
│   ├── redis-service.yaml
│   ├── rabbitmq-service.yaml
│   └── minio-service.yaml
├── statefulsets/                # Stateful applications
│   ├── postgres-statefulset.yaml
│   ├── redis-statefulset.yaml
│   ├── rabbitmq-statefulset.yaml
│   └── minio-statefulset.yaml
├── ingress/                     # Ingress configurations
│   ├── traefik-config.yaml
│   └── cognive-ingress.yaml
├── configmaps/                  # Configuration maps
│   └── app-config.yaml
├── secrets/                     # Secret templates
│   └── secrets.yaml.example
├── monitoring/                  # Monitoring stack
│   ├── prometheus/
│   └── grafana/
└── scripts/                     # Deployment scripts
    ├── deploy.sh
    ├── setup-kubectl.sh
    └── health-check.sh
```

## 🚀 Quick Start

### Prerequisites

- k3s or MicroK8s installed (see [terraform/modules/k3s](../terraform/modules/k3s))
- kubectl configured
- At least 8GB RAM, 4 vCPU, 100GB storage

### 1. Install k3s (if not already installed)

```bash
# Using Terraform
cd terraform/modules/k3s
terraform init
terraform apply

# Or manual installation
curl -sfL https://get.k3s.io | sh -

# Configure kubectl
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config
```

### 2. Create Namespace and RBAC

```bash
cd k8s
kubectl apply -f namespace.yaml
kubectl apply -f rbac/
```

### 3. Create Secrets

```bash
# Copy the example and fill in your values
cp secrets/secrets.yaml.example secrets/secrets.yaml
vim secrets/secrets.yaml  # Edit with your secrets

# Apply secrets
kubectl apply -f secrets/secrets.yaml
```

### 4. Deploy Storage Layer (PostgreSQL, Redis, RabbitMQ, MinIO)

```bash
kubectl apply -f statefulsets/
kubectl apply -f services/
```

### 5. Deploy Application Layer

```bash
kubectl apply -f configmaps/
kubectl apply -f deployments/
```

### 6. Deploy Ingress Controller

```bash
kubectl apply -f ingress/
```

### 7. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n cognive

# Check services
kubectl get svc -n cognive

# Check ingress
kubectl get ingress -n cognive

# Run health checks
./scripts/health-check.sh
```

## 📊 Monitoring Setup

### Deploy Prometheus and Grafana

```bash
kubectl apply -f monitoring/prometheus/
kubectl apply -f monitoring/grafana/
```

### Access Monitoring UIs

```bash
# Port-forward Grafana
kubectl port-forward -n cognive svc/grafana 3000:3000

# Access at http://localhost:3000
# Default credentials: admin/admin
```

## 🔐 RBAC Configuration

The following service accounts and roles are configured:

- **cognive-api**: API service account with read/write access to ConfigMaps and Secrets
- **cognive-celery**: Celery worker service account with limited permissions
- **cognive-monitoring**: Monitoring service account for Prometheus
- **cognive-admin**: Admin role for cluster management

## 🌐 Ingress Configuration

Traefik is configured as the default ingress controller with:

- **HTTP**: Port 80 (redirects to HTTPS)
- **HTTPS**: Port 443 (TLS termination)
- **Let's Encrypt**: Automatic TLS certificate provisioning

### Endpoints

- API: `https://api.yourdomain.com`
- Dashboard: `https://dashboard.yourdomain.com`
- Grafana: `https://grafana.yourdomain.com`
- MinIO Console: `https://minio.yourdomain.com`

## 🔄 Scaling

### Horizontal Pod Autoscaling

```bash
# API deployment auto-scales based on CPU
kubectl get hpa -n cognive

# Manually scale
kubectl scale deployment/cognive-api --replicas=5 -n cognive
```

### Vertical Scaling

Edit resource requests/limits in deployment files:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

## 🛠️ Troubleshooting

### Check Logs

```bash
# API logs
kubectl logs -f deployment/cognive-api -n cognive

# Celery logs
kubectl logs -f deployment/cognive-celery -n cognive

# All pods
kubectl logs -f -l app=cognive -n cognive
```

### Pod Status

```bash
# Describe pod
kubectl describe pod <pod-name> -n cognive

# Get events
kubectl get events -n cognive --sort-by='.lastTimestamp'
```

### Database Connection

```bash
# Port-forward PostgreSQL
kubectl port-forward -n cognive svc/postgres 5432:5432

# Test connection
psql -h localhost -U cognive -d cognive
```

## 📋 Maintenance

### Update Deployments

```bash
# Rolling update
kubectl set image deployment/cognive-api \
  api=cognive-api:v1.1.0 -n cognive

# Check rollout status
kubectl rollout status deployment/cognive-api -n cognive

# Rollback if needed
kubectl rollout undo deployment/cognive-api -n cognive
```

### Backup and Restore

```bash
# Backup PostgreSQL
kubectl exec -n cognive postgres-0 -- \
  pg_dump -U cognive cognive > backup.sql

# Restore PostgreSQL
kubectl exec -i -n cognive postgres-0 -- \
  psql -U cognive cognive < backup.sql
```

## 🔒 Security

- All secrets are stored in Kubernetes Secrets (base64 encoded)
- TLS certificates managed by Let's Encrypt
- Network policies restrict pod-to-pod communication
- RBAC enforces least-privilege access
- Pod security policies enabled

## 📚 Additional Resources

- [k3s Documentation](https://docs.k3s.io/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Cognive Architecture](../cognive-docs/CONTROL_PLANE_ARCHITECTURE.md)
- [Tech Stack](../cognive-docs/TECH_STACK.md)


