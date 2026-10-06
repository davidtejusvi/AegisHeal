# AegisHeal — AI-Powered Self-Healing Infrastructure Platform

> Automated anomaly detection and remediation for AWS-hosted workloads.
> Detects failures using a dual-model AI stack (Isolation Forest + LSTM), identifies root causes, and triggers fixes — all without human intervention.

---

## Architecture

```
Internet
   │
   ▼
AWS ALB (internal)
   │
   ├──► anomaly-detector   :8000  (FastAPI · IsolationForest + LSTM)
   │         │
   │         └──► /analyze · /train · /anomalies · /metrics
   │
   └──► remediation-engine :8001  (FastAPI · RCA + action handler)
             │
             ├──► PostgreSQL RDS  (incident history)
             ├──► Prometheus      (metrics scraping)
             ├──► AWS Lambda      (auto-scaler, instance-restarter, alert-processor)
             └──► CloudWatch      (alarms, composite alarm, SNS)
```

Both services run on **EKS** (managed node group, K8s 1.29) in the `monitoring-platform` namespace, behind a Kustomize-managed manifest set with HPA, PDB, NetworkPolicy, and IRSA.

---

## Repository Structure

```
AegisHeal/
├── src/
│   ├── anomaly-detector/       FastAPI service — ML anomaly scoring
│   ├── remediation-engine/     FastAPI service — RCA + auto-remediation
│   └── lambda-functions/
│       ├── alert-processor/    Routes SNS alerts → remediation-engine
│       ├── auto-scaler/        Scales EKS node groups on CloudWatch alarm
│       ├── instance-restarter/ Restarts stopped EC2 instances
│       └── metrics-collector/  Pushes custom metrics to CloudWatch (1 min schedule)
│
├── terraform/
│   ├── main.tf                 Root module — wires all sub-modules
│   ├── variables.tf / outputs.tf / provider.tf / versions.tf
│   ├── github-actions-oidc.tf  GitHub Actions OIDC provider + deploy role
│   ├── modules/
│   │   ├── vpc/                VPC, subnets, NAT GWs, flow logs
│   │   ├── eks/                EKS cluster, node group, OIDC provider, autoscaler IRSA
│   │   ├── iam/                Lambda roles, IRSA roles for K8s SAs, SSM automation
│   │   ├── rds/                PostgreSQL 15, Secrets Manager password, enhanced monitoring
│   │   ├── lambda/             All 4 Lambda functions, EventBridge rules, SNS subscription
│   │   └── cloudwatch/         SNS topic, metric alarms, composite alarm, dashboard
│   └── environments/
│       ├── dev/                Dev-specific tfvars (t3.medium nodes, single-AZ RDS)
│       └── prod/               Prod-specific tfvars (t3.large nodes, Multi-AZ RDS)
│
├── k8s/
│   ├── base/                   Kustomize base — all K8s resources
│   │   ├── namespace.yaml
│   │   ├── rbac.yaml           ServiceAccounts, ClusterRole, Roles with IRSA annotations
│   │   ├── configmap.yaml      Non-secret env vars for both services
│   │   ├── secret.yaml         ExternalSecret CRD (pulls from Secrets Manager via ESO)
│   │   ├── cluster-secret-store.yaml  ESO ClusterSecretStore → AWS SecretsManager
│   │   ├── anomaly-detector-deployment.yaml
│   │   ├── anomaly-detector-service.yaml
│   │   ├── remediation-engine-deployment.yaml
│   │   ├── remediation-engine-service.yaml
│   │   ├── hpa.yaml            HPA for both services (CPU + memory triggers)
│   │   ├── pdb.yaml            PodDisruptionBudget (min 1 available each)
│   │   ├── network-policy.yaml Ingress/egress per service
│   │   ├── ingress.yaml        AWS ALB ingress (/anomaly, /remediation)
│   │   ├── prometheus.yaml     Prometheus deployment + service discovery config
│   │   └── grafana.yaml        Grafana + 10-panel dashboard ConfigMap
│   └── overlays/
│       ├── dev/                1 replica, DRY_RUN=true, dev image tags
│       └── prod/               3 replicas, tighter HPA, internet-facing ALB
│
├── monitoring/
│   └── cloudwatch/alarms.tf    Standalone extra alarms (EKS ContainerInsights, RDS, Lambda)
│
├── .github/workflows/
│   └── deploy-k8s.yml          Build → push ECR → deploy to EKS (OIDC auth, no static keys)
│
├── scripts/
│   ├── bootstrap.sh            One-shot: terraform apply + kubeconfig + ESO helm + kubectl apply
│   └── build-push.sh           Local ECR build/push for anomaly-detector / remediation-engine
│
└── docs/
    ├── architecture.md         Full system design, data flow, security model
    ├── runbook.md              Prerequisites, bootstrap, troubleshooting, incident response
    └── api-reference.md        All 10 API endpoints with request/response schemas + curl examples
```

---

## Key Metrics

| Metric | Target |
|--------|--------|
| MTTD — Mean Time to Detect | < 2 min |
| MTTR — Mean Time to Recover | < 10 min |
| Auto-remediation rate | > 80 % |
| False positive rate | < 5 % |

---

## Quick Start

```bash
# 1. Bootstrap everything (Terraform + EKS + ESO + K8s manifests)
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh

# 2. Or step by step:
cd terraform
terraform init
terraform apply -var="environment=dev" -var="alert_email=you@example.com"

aws eks update-kubeconfig --region us-east-1 \
  --name ai-monitoring-platform-dev-eks

helm repo add external-secrets https://charts.external-secrets.io
helm upgrade --install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace

kubectl apply -k k8s/overlays/dev
```

### Test the platform

```bash
# Health checks
kubectl get pods -n monitoring-platform
curl http://<ALB>/anomaly/health
curl http://<ALB>/remediation/health

# Trigger a simulated incident (dry-run)
curl -X POST http://<ALB>/remediation/simulate \
  -H 'Content-Type: application/json' \
  -d '{"service": "api-gateway", "failure_type": "cpu_spike"}'
```

---

## CI/CD

Push to `main` → GitHub Actions:
1. Validates K8s manifests with kubeval + kustomize build
2. Builds & pushes both Docker images to ECR (OIDC — no static AWS keys)
3. Deploys to EKS with `kustomize build | kubectl apply`
4. Waits for rollouts to complete

Secrets needed in GitHub repo settings:
- `AWS_DEPLOY_ROLE_ARN` — output of `terraform output github_actions_role_arn`

---

## Security Highlights

- **IRSA** — K8s ServiceAccounts assume scoped IAM roles; no node-level credentials
- **External Secrets Operator** — DB password pulled from Secrets Manager at runtime; no secrets in Git
- **NetworkPolicy** — each pod has explicit allow-lists for ingress and egress
- **IMDSv2** — enforced on all EKS nodes via launch template
- **Encrypted storage** — EBS volumes (gp3) and RDS encrypted at rest
- **VPC flow logs** — all traffic logged to CloudWatch
- **GitHub Actions OIDC** — CI uses short-lived tokens, not long-lived IAM keys

---

## Docs

- [Architecture](docs/architecture.md)
- [Runbook](docs/runbook.md)
- [API Reference](docs/api-reference.md)
