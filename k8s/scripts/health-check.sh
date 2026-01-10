#!/bin/bash
# =============================================================================
# Cognive Kubernetes Health Check Script
# =============================================================================
# This script checks the health of all Cognive components
#
# Usage:
#   ./health-check.sh
#   ./health-check.sh --detailed
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="cognive"
DETAILED=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --detailed)
            DETAILED=true
            shift
            ;;
        *)
            echo "Usage: $0 [--detailed]"
            exit 1
            ;;
    esac
done

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_ok() { echo -e "${GREEN}[✓]${NC} $1"; }
log_fail() { echo -e "${RED}[✗]${NC} $1"; }

echo ""
log_info "Cognive Kubernetes Health Check"
log_info "================================"
echo ""

# Check if namespace exists
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    log_error "Namespace $NAMESPACE not found"
    exit 1
fi

# Function to check pod health
check_pods() {
    local component=$1
    local label=$2
    
    echo -n "Checking $component... "
    
    local pods=$(kubectl get pods -n $NAMESPACE -l $label -o json)
    local total=$(echo $pods | jq -r '.items | length')
    local ready=$(echo $pods | jq -r '[.items[] | select(.status.phase=="Running" and ([.status.conditions[] | select(.type=="Ready" and .status=="True")] | length > 0))] | length')
    
    if [ $total -eq 0 ]; then
        log_fail "$component: No pods found"
        return 1
    elif [ $ready -eq $total ]; then
        log_ok "$component: $ready/$total pods ready"
        return 0
    else
        log_warn "$component: $ready/$total pods ready"
        if [ "$DETAILED" = true ]; then
            kubectl get pods -n $NAMESPACE -l $label
        fi
        return 1
    fi
}

# Function to check endpoint health
check_endpoint() {
    local name=$1
    local url=$2
    
    echo -n "Checking $name endpoint... "
    
    # Port forward and test
    local pod=$(kubectl get pods -n $NAMESPACE -l component=api -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$pod" ]; then
        log_fail "$name: No API pod found"
        return 1
    fi
    
    local response=$(kubectl exec -n $NAMESPACE $pod -- curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$url 2>/dev/null || echo "000")
    
    if [ "$response" = "200" ]; then
        log_ok "$name: HTTP $response"
        return 0
    else
        log_fail "$name: HTTP $response"
        return 1
    fi
}

# Check cluster connection
echo "=== Cluster Status ==="
if kubectl cluster-info &> /dev/null; then
    log_ok "Cluster is accessible"
else
    log_fail "Cannot connect to cluster"
    exit 1
fi
echo ""

# Check nodes
echo "=== Node Status ==="
kubectl get nodes
echo ""

# Check storage layer
echo "=== Storage Layer ==="
check_pods "PostgreSQL" "component=postgres"
check_pods "Redis" "component=redis"
check_pods "RabbitMQ" "component=rabbitmq"
check_pods "MinIO" "component=minio"
echo ""

# Check application layer
echo "=== Application Layer ==="
check_pods "API" "component=api"
check_pods "Celery" "component=celery"
check_pods "Flower" "component=flower"
echo ""

# Check endpoints
echo "=== API Health Endpoints ==="
check_endpoint "Liveness" "/api/v1/health/liveness"
check_endpoint "Readiness" "/api/v1/health/readiness"
echo ""

# Check ingress
echo "=== Ingress Status ==="
if kubectl get ingress -n $NAMESPACE &> /dev/null; then
    kubectl get ingress -n $NAMESPACE
else
    log_warn "No ingress configured"
fi
echo ""

# Check monitoring (if enabled)
echo "=== Monitoring Stack ==="
if kubectl get deployment prometheus -n $NAMESPACE &> /dev/null; then
    check_pods "Prometheus" "app=prometheus"
    check_pods "Grafana" "app=grafana"
else
    log_warn "Monitoring not deployed"
fi
echo ""

# Check persistent volumes
if [ "$DETAILED" = true ]; then
    echo "=== Persistent Volumes ==="
    kubectl get pvc -n $NAMESPACE
    echo ""
fi

# Check recent events
if [ "$DETAILED" = true ]; then
    echo "=== Recent Events ==="
    kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -20
    echo ""
fi

# Summary
echo "=== Summary ==="
total_pods=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
running_pods=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)

log_info "Total pods: $total_pods"
log_info "Running pods: $running_pods"

if [ $running_pods -eq $total_pods ] && [ $total_pods -gt 0 ]; then
    echo ""
    log_ok "All systems operational!"
    exit 0
else
    echo ""
    log_warn "Some components are not healthy"
    log_info "Run with --detailed for more information"
    exit 1
fi








