# AegisHeal — Operations Runbook

## Prerequisites

| Tool | Minimum Version | Install |
|---|---|---|
| terraform | >= 1.6.0 | https://developer.hashicorp.com/terraform/downloads |
| kubectl | >= 1.28 | https://kubernetes.io/docs/tasks/tools/ |
| aws cli | >= 2.13 | https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html |
| helm | >= 3.12 | https://helm.sh/docs/intro/install/ |
| kustomize | >= 5.0 | https://kubectl.docs.kubernetes.io/installation/kustomize/ |
| docker | >= 24.0 | https://docs.docker.com/engine/install/ |

Ensure `aws configure` is set up with a profile that has AdministratorAccess (for first bootstrap only; use the GitHub Actions OIDC role for CI).

## Bootstrap Steps

```bash
# 1. Clone and enter the repo
git clone https://github.com/YOUR_ORG/AegisHeal.git
cd AegisHeal

# 2. Run the bootstrap script (interactive)
bash scripts/bootstrap.sh

# OR run steps manually:

# 2a. Terraform
cd terraform/
terraform init
terraform plan -var="environment=dev" -var="alert_email=you@example.com"
terraform apply -var="environment=dev" -var="alert_email=you@example.com"

# 2b. Configure kubectl
aws eks update-kubeconfig \
  --region us-east-1 \
  --name ai-monitoring-platform-dev-eks

# 2c. Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm upgrade --install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace

# 2d. Apply K8s manifests
kubectl apply -k k8s/overlays/dev

# 2e. Verify pods
kubectl get pods -n monitoring-platform
```

## Checking Service Health

```bash
# Pod status
kubectl get pods -n monitoring-platform
kubectl describe pod <pod-name> -n monitoring-platform

# Health endpoints (port-forward for local access)
kubectl port-forward svc/anomaly-detector-service 8000:8000 -n monitoring-platform &
kubectl port-forward svc/remediation-engine-service 8001:8001 -n monitoring-platform &

curl http://localhost:8000/health
curl http://localhost:8001/health

# Logs
kubectl logs -l app=anomaly-detector -n monitoring-platform --tail=100
kubectl logs -l app=remediation-engine -n monitoring-platform --tail=100
```

## Triggering a Test Anomaly

```bash
# Port-forward remediation-engine
kubectl port-forward svc/remediation-engine-service 8001:8001 -n monitoring-platform

# Simulate a CPU spike (dry-run — no actual changes made)
curl -X POST http://localhost:8001/simulate \
  -H 'Content-Type: application/json' \
  -d '{"service": "anomaly-detector", "failure_type": "cpu_spike"}'

# Other failure types: memory_pressure, high_error_rate, latency_spike
```

## Retraining the Anomaly Detector

```bash
kubectl port-forward svc/anomaly-detector-service 8000:8000 -n monitoring-platform

curl -X POST http://localhost:8000/train \
  -H 'Content-Type: application/json' \
  -d '{
    "service": "anomaly-detector",
    "history": [
      {"cpu_utilization": 45.0, "memory_utilization": 60.0, "request_count": 100.0, "error_rate": 0.01, "latency_p99": 0.3},
      ... (at least 21 samples required)
    ]
  }'
```

## Troubleshooting

### Pod CrashLoopBackOff
```bash
kubectl describe pod <pod> -n monitoring-platform
kubectl logs <pod> -n monitoring-platform --previous
# Common causes: missing secret (check ESO sync), wrong image tag, OOM
```

### OOM Kills
```bash
kubectl describe pod <pod> -n monitoring-platform | grep -i oom
# Fix: increase memory limit in k8s/base/*-deployment.yaml, re-apply
kubectl top pod -n monitoring-platform
```

### ESO Secret Sync Failures
```bash
kubectl get externalsecret -n monitoring-platform
kubectl describe externalsecret aegisheal-db-secret -n monitoring-platform
# Check ESO logs
kubectl logs -l app.kubernetes.io/name=external-secrets -n external-secrets
# Verify IRSA: check pod annotation matches IAM role ARN
kubectl get sa -n external-secrets external-secrets -o yaml
```

### IRSA Permission Denied
```bash
# Verify ServiceAccount annotation
kubectl get sa anomaly-detector -n monitoring-platform -o yaml
# Should have: eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/...
# Check IAM role trust policy matches the cluster OIDC URL
aws iam get-role --role-name ai-monitoring-platform-dev-anomaly-detector-irsa
```

## Scaling

### HPA
The HPA targets 60% CPU utilisation, scaling between 2-8 replicas per service. Check HPA status:
```bash
kubectl get hpa -n monitoring-platform
kubectl describe hpa anomaly-detector-hpa -n monitoring-platform
```

### Manual Scaling
```bash
kubectl scale deployment anomaly-detector --replicas=4 -n monitoring-platform
```

### Update HPA Thresholds
Edit `k8s/base/hpa.yaml`, update `targetAverageUtilization`, then:
```bash
kubectl apply -k k8s/overlays/dev
```

## Monitoring

- **Grafana**: `kubectl port-forward svc/grafana-service 3000:3000 -n monitoring-platform` → http://localhost:3000 (admin / see grafana-secret)
- **Prometheus**: `kubectl port-forward svc/prometheus-service 9090:9090 -n monitoring-platform` → http://localhost:9090

Key Prometheus queries:
```promql
# Anomaly detection rate
rate(anomaly_analyze_requests_total[5m])

# Auto-resolution rate
rate(remediation_auto_resolved_total[5m]) / rate(remediation_incidents_total[5m]) * 100

# p99 latency
histogram_quantile(0.99, rate(anomaly_analyze_duration_seconds_bucket[5m]))

# Active incidents
remediation_active_incidents
```

## Incident Response

Alert flow:
```
1. CloudWatch metric threshold breached
2. CloudWatch Alarm triggers → publishes to SNS topic
3. SNS → Lambda alert-processor function
4. alert-processor enriches payload and POSTs to remediation-engine /remediate
5. remediation-engine runs RCA, selects action, executes
6. Incident recorded in memory (GET /incidents) and metrics emitted
7. If auto-resolution fails, on-call engineer is paged via SNS email subscription
```

To check recent incidents:
```bash
kubectl port-forward svc/remediation-engine-service 8001:8001 -n monitoring-platform
curl http://localhost:8001/incidents
curl http://localhost:8001/stats
```
