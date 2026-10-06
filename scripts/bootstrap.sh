#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# AegisHeal Bootstrap Script
# Provisions AWS infrastructure and deploys K8s manifests.
# Usage: bash scripts/bootstrap.sh
# =============================================================================

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"

info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
error() { echo "[ERROR] $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Check prerequisites
# ---------------------------------------------------------------------------
check_tool() {
  local tool=$1 min_version=$2
  if ! command -v "$tool" &>/dev/null; then
    error "$tool is not installed. See docs/runbook.md for installation instructions."
  fi
  local version
  version=$("$tool" version 2>/dev/null || "$tool" --version 2>/dev/null | head -1)
  info "$tool: $version"
}

info "=== Checking prerequisites ==="
check_tool terraform "1.6.0"
check_tool kubectl    "1.28"
check_tool aws        "2.13"
check_tool helm       "3.12"
check_tool kustomize  "5.0"

# ---------------------------------------------------------------------------
# 2. Gather inputs
# ---------------------------------------------------------------------------
info "=== Gathering configuration ==="

read -r -p "AWS Account ID: " AWS_ACCOUNT_ID
[[ -z "$AWS_ACCOUNT_ID" ]] && error "AWS_ACCOUNT_ID cannot be empty"

read -r -p "AWS Region [us-east-1]: " AWS_REGION
AWS_REGION=${AWS_REGION:-us-east-1}

read -r -p "Environment (dev/staging/prod) [dev]: " ENVIRONMENT
ENVIRONMENT=${ENVIRONMENT:-dev}

read -r -p "Alert email address: " ALERT_EMAIL
[[ -z "$ALERT_EMAIL" ]] && error "ALERT_EMAIL cannot be empty"

export AWS_DEFAULT_REGION="$AWS_REGION"

# ---------------------------------------------------------------------------
# 3. Terraform apply
# ---------------------------------------------------------------------------
info "=== Running Terraform ==="
cd "$REPO_ROOT/terraform"

terraform init -upgrade
terraform plan \
  -var="environment=${ENVIRONMENT}" \
  -var="alert_email=${ALERT_EMAIL}" \
  -var="aws_region=${AWS_REGION}" \
  -out=tfplan

terraform apply tfplan

# ---------------------------------------------------------------------------
# 4. Configure kubectl
# ---------------------------------------------------------------------------
info "=== Configuring kubectl ==="
aws eks update-kubeconfig \
  --region "$AWS_REGION" \
  --name "ai-monitoring-platform-${ENVIRONMENT}-eks"

kubectl cluster-info

# ---------------------------------------------------------------------------
# 5. Install External Secrets Operator
# ---------------------------------------------------------------------------
info "=== Installing External Secrets Operator ==="
helm repo add external-secrets https://charts.external-secrets.io || true
helm repo update
helm upgrade --install external-secrets external-secrets/external-secrets \
  -n external-secrets \
  --create-namespace \
  --wait \
  --timeout 5m

kubectl rollout status deployment/external-secrets -n external-secrets --timeout=3m

# ---------------------------------------------------------------------------
# 6. Apply K8s manifests
# ---------------------------------------------------------------------------
info "=== Applying K8s manifests (overlay: ${ENVIRONMENT}) ==="
cd "$REPO_ROOT"
kubectl apply -k "k8s/overlays/${ENVIRONMENT}"

# ---------------------------------------------------------------------------
# 7. Wait for rollouts
# ---------------------------------------------------------------------------
info "=== Waiting for rollouts ==="
kubectl rollout status deployment/anomaly-detector  -n monitoring-platform --timeout=5m
kubectl rollout status deployment/remediation-engine -n monitoring-platform --timeout=5m
kubectl rollout status deployment/grafana            -n monitoring-platform --timeout=3m || true

# ---------------------------------------------------------------------------
# 8. Print health check URLs
# ---------------------------------------------------------------------------
info "=== Deployment complete ==="
INGRESS_HOSTNAME=$(kubectl get ingress -n monitoring-platform -o jsonpath='{.items[0].status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo '<pending>')

echo ""
echo "  Anomaly Detector:   http://${INGRESS_HOSTNAME}/anomaly/health"
echo "  Remediation Engine: http://${INGRESS_HOSTNAME}/remediation/health"
echo "  Grafana (port-fwd): kubectl port-forward svc/grafana-service 3000:3000 -n monitoring-platform"
echo "  Prometheus:         kubectl port-forward svc/prometheus-service 9090:9090 -n monitoring-platform"
echo ""
info "Bootstrap complete!"
