#!/bin/bash
# =============================================================================
# Cognive Kubernetes Deployment Script
# =============================================================================
# This script deploys the complete Cognive stack to Kubernetes
#
# Usage:
#   ./deploy.sh                    # Deploy all components
#   ./deploy.sh --dry-run          # Show what would be deployed
#   ./deploy.sh --component api    # Deploy specific component
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }
log_success() { echo -e "${CYAN}[SUCCESS]${NC} $1"; }

# Default values
DRY_RUN=false
COMPONENT=""
NAMESPACE="cognive"
SKIP_MONITORING=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --component)
            COMPONENT="$2"
            shift 2
            ;;
        --skip-monitoring)
            SKIP_MONITORING=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run             Show what would be deployed without applying"
            echo "  --component <name>    Deploy specific component (api, storage, ingress, monitoring)"
            echo "  --skip-monitoring     Skip deploying monitoring stack"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Determine kubectl command
KUBECTL_CMD="kubectl"
if [ "$DRY_RUN" = true ]; then
    KUBECTL_CMD="kubectl apply --dry-run=client"
    log_warn "DRY RUN MODE: No changes will be applied"
fi

log_info "Cognive Kubernetes Deployment"
log_info "=============================="
echo ""

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    log_error "kubectl is not configured or cluster is not accessible"
    log_info "Run ./setup-kubectl.sh first"
    exit 1
fi

log_info "Deploying to namespace: $NAMESPACE"
echo ""

# Function to apply manifests
apply_manifest() {
    local manifest_path=$1
    local description=$2
    
    if [ -f "$manifest_path" ]; then
        log_info "Applying: $description"
        $KUBECTL_CMD -f "$manifest_path"
    elif [ -d "$manifest_path" ]; then
        log_info "Applying: $description"
        $KUBECTL_CMD -f "$manifest_path"
    else
        log_warn "Skipping: $manifest_path (not found)"
    fi
}

# Function to wait for deployment
wait_for_deployment() {
    local deployment=$1
    local namespace=$2
    
    if [ "$DRY_RUN" = false ]; then
        log_info "Waiting for $deployment to be ready..."
        kubectl rollout status deployment/$deployment -n $namespace --timeout=5m
    fi
}

# Function to wait for statefulset
wait_for_statefulset() {
    local statefulset=$1
    local namespace=$2
    
    if [ "$DRY_RUN" = false ]; then
        log_info "Waiting for $statefulset to be ready..."
        kubectl rollout status statefulset/$statefulset -n $namespace --timeout=5m
    fi
}

# Change to k8s directory
cd "$(dirname "$0")/.."

# Deploy based on component
case "$COMPONENT" in
    "")
        # Full deployment
        log_step "1/7 Creating namespace..."
        apply_manifest "namespace.yaml" "Cognive namespace"
        echo ""
        
        log_step "2/7 Setting up RBAC..."
        apply_manifest "rbac/" "RBAC configurations"
        echo ""
        
        log_step "3/7 Creating secrets..."
        if [ ! -f "secrets/secrets.yaml" ]; then
            log_error "secrets/secrets.yaml not found!"
            log_info "Copy secrets.yaml.example to secrets.yaml and fill in your values"
            exit 1
        fi
        apply_manifest "secrets/secrets.yaml" "Secrets"
        echo ""
        
        log_step "4/7 Deploying storage layer..."
        apply_manifest "statefulsets/" "Storage StatefulSets"
        wait_for_statefulset "postgres" "$NAMESPACE"
        wait_for_statefulset "redis" "$NAMESPACE"
        wait_for_statefulset "rabbitmq" "$NAMESPACE"
        wait_for_statefulset "minio" "$NAMESPACE"
        echo ""
        
        log_step "5/7 Deploying application layer..."
        apply_manifest "configmaps/" "ConfigMaps"
        apply_manifest "deployments/" "Application deployments"
        wait_for_deployment "cognive-api" "$NAMESPACE"
        wait_for_deployment "cognive-celery" "$NAMESPACE"
        echo ""
        
        log_step "6/7 Deploying ingress..."
        apply_manifest "ingress/" "Ingress configurations"
        echo ""
        
        if [ "$SKIP_MONITORING" = false ]; then
            log_step "7/7 Deploying monitoring..."
            apply_manifest "monitoring/" "Monitoring stack"
            wait_for_deployment "prometheus" "$NAMESPACE"
            wait_for_deployment "grafana" "$NAMESPACE"
        else
            log_warn "Skipping monitoring deployment"
        fi
        ;;
        
    "api")
        log_info "Deploying API component only..."
        apply_manifest "deployments/api-deployment.yaml" "API deployment"
        wait_for_deployment "cognive-api" "$NAMESPACE"
        ;;
        
    "storage")
        log_info "Deploying storage layer only..."
        apply_manifest "statefulsets/" "Storage StatefulSets"
        ;;
        
    "ingress")
        log_info "Deploying ingress only..."
        apply_manifest "ingress/" "Ingress configurations"
        ;;
        
    "monitoring")
        log_info "Deploying monitoring stack only..."
        apply_manifest "monitoring/" "Monitoring stack"
        ;;
        
    *)
        log_error "Unknown component: $COMPONENT"
        exit 1
        ;;
esac

echo ""
log_success "Deployment complete!"
echo ""

if [ "$DRY_RUN" = false ]; then
    log_info "Checking deployment status..."
    echo ""
    kubectl get all -n $NAMESPACE
    echo ""
    
    log_info "Next steps:"
    log_info "1. Check pod status: kubectl get pods -n $NAMESPACE"
    log_info "2. View logs: kubectl logs -f deployment/cognive-api -n $NAMESPACE"
    log_info "3. Run health check: ./health-check.sh"
    log_info "4. Access services via Ingress or port-forward"
    echo ""
    
    log_info "Port forwarding examples:"
    log_info "  API:      kubectl port-forward -n $NAMESPACE svc/cognive-api 8000:80"
    log_info "  Grafana:  kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
    log_info "  Flower:   kubectl port-forward -n $NAMESPACE svc/cognive-flower 5555:5555"
fi






