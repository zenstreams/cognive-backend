#!/bin/bash
# =============================================================================
# Cognive Kubernetes - kubectl Setup Script
# =============================================================================
# This script configures kubectl to access your k3s/MicroK8s cluster
#
# Usage:
#   ./setup-kubectl.sh
#   ./setup-kubectl.sh --remote <server-ip>
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Parse arguments
REMOTE_MODE=false
SERVER_IP=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --remote)
            REMOTE_MODE=true
            SERVER_IP="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Usage: $0 [--remote <server-ip>]"
            exit 1
            ;;
    esac
done

log_info "Cognive Kubernetes kubectl Setup"
log_info "================================"
echo ""

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl is not installed"
    log_info "Install kubectl: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

log_step "1/5 Detecting Kubernetes distribution..."

# Detect k3s or MicroK8s
if command -v k3s &> /dev/null; then
    log_info "Detected: k3s"
    K8S_TYPE="k3s"
elif command -v microk8s &> /dev/null; then
    log_info "Detected: MicroK8s"
    K8S_TYPE="microk8s"
else
    log_error "Neither k3s nor MicroK8s detected"
    log_info "Please install k3s or MicroK8s first"
    exit 1
fi

log_step "2/5 Creating kubectl configuration directory..."

# Create .kube directory if it doesn't exist
mkdir -p ~/.kube

# Backup existing config
if [ -f ~/.kube/config ]; then
    log_warn "Existing kubeconfig found, creating backup..."
    cp ~/.kube/config ~/.kube/config.backup.$(date +%Y%m%d_%H%M%S)
fi

log_step "3/5 Copying kubeconfig..."

if [ "$REMOTE_MODE" = true ]; then
    log_info "Remote mode: Configuring for remote server $SERVER_IP"
    
    if [ "$K8S_TYPE" = "k3s" ]; then
        # Copy kubeconfig from remote k3s server
        log_info "Fetching kubeconfig from remote k3s server..."
        ssh root@${SERVER_IP} "cat /etc/rancher/k3s/k3s.yaml" > ~/.kube/config.tmp
        
        # Replace localhost with actual server IP
        sed "s/127.0.0.1/${SERVER_IP}/g" ~/.kube/config.tmp > ~/.kube/config
        rm ~/.kube/config.tmp
    else
        log_error "Remote mode is only supported for k3s"
        exit 1
    fi
else
    log_info "Local mode: Configuring for local cluster"
    
    if [ "$K8S_TYPE" = "k3s" ]; then
        # Check if running as root
        if [[ $EUID -eq 0 ]]; then
            cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config
        else
            sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config
        fi
    elif [ "$K8S_TYPE" = "microk8s" ]; then
        microk8s config > ~/.kube/config
    fi
fi

log_step "4/5 Setting correct permissions..."

chmod 600 ~/.kube/config

log_step "5/5 Verifying configuration..."

# Test connection
if kubectl cluster-info &> /dev/null; then
    log_info "✓ kubectl successfully configured!"
    echo ""
    log_info "Cluster information:"
    kubectl cluster-info
    echo ""
    log_info "Available nodes:"
    kubectl get nodes
    echo ""
    log_info "Kubeconfig location: ~/.kube/config"
else
    log_error "Failed to connect to cluster"
    log_info "Please check your configuration and try again"
    exit 1
fi

log_info ""
log_info "Next steps:"
log_info "1. Verify cluster access: kubectl get nodes"
log_info "2. Check namespaces: kubectl get namespaces"
log_info "3. Deploy Cognive: cd ../.. && kubectl apply -f k8s/"
log_info ""
log_info "Setup complete! ✓"


