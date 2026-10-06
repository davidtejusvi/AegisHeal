#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# AegisHeal — Build and push Docker images to ECR
# Usage: bash scripts/build-push.sh [SERVICE] [TAG]
#   SERVICE: anomaly-detector | remediation-engine | all  (default: all)
#   TAG:     image tag                                     (default: latest)
# =============================================================================

SERVICE=${1:-all}
TAG=${2:-latest}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"

info()  { echo "[INFO]  $*"; }
error() { echo "[ERROR] $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Resolve AWS account and region
# ---------------------------------------------------------------------------
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_DEFAULT_REGION:-${AWS_REGION:-us-east-1}}
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

info "Account:  $AWS_ACCOUNT_ID"
info "Region:   $AWS_REGION"
info "Registry: $ECR_REGISTRY"
info "Service:  $SERVICE"
info "Tag:      $TAG"

# ---------------------------------------------------------------------------
# ECR login
# ---------------------------------------------------------------------------
info "=== Logging into ECR ==="
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# ---------------------------------------------------------------------------
# Build and push function
# ---------------------------------------------------------------------------
build_push() {
  local svc=$1
  local repo="${ECR_REGISTRY}/aegisheal/${svc}"
  local ctx="${REPO_ROOT}/src/${svc}"

  if [[ ! -d "$ctx" ]]; then
    error "Source directory not found: $ctx"
  fi

  # Ensure ECR repository exists
  aws ecr describe-repositories --repository-names "aegisheal/${svc}" \
    --region "$AWS_REGION" &>/dev/null || \
  aws ecr create-repository --repository-name "aegisheal/${svc}" \
    --region "$AWS_REGION" \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 >/dev/null

  info "=== Building ${svc}:${TAG} ==="
  docker build \
    --platform linux/amd64 \
    --tag "${repo}:${TAG}" \
    --tag "${repo}:latest" \
    "$ctx"

  info "=== Pushing ${svc}:${TAG} ==="
  docker push "${repo}:${TAG}"
  docker push "${repo}:latest"

  info "Image pushed: ${repo}:${TAG}"
}

# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
case "$SERVICE" in
  anomaly-detector)
    build_push anomaly-detector
    ;;
  remediation-engine)
    build_push remediation-engine
    ;;
  dashboard)
    build_push dashboard
    ;;
  all)
    build_push anomaly-detector
    build_push remediation-engine
    build_push dashboard
    ;;
  *)
    error "Unknown service '$SERVICE'. Use: anomaly-detector | remediation-engine | dashboard | all"
    ;;
esac

info "Done."
