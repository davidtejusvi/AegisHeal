# AegisHeal — Architecture

## System Overview

AegisHeal is an AI-powered self-healing infrastructure platform deployed on Amazon EKS. It continuously monitors service health metrics, detects anomalies using machine learning, and automatically triggers remediation workflows — reducing mean time to recovery (MTTR) and minimising human intervention for common failure modes.

The platform has two core services:
- **anomaly-detector**: Ingests metric snapshots, runs them through a dual-model pipeline (IsolationForest for statistical outliers + LSTM for temporal patterns), scores the anomaly severity, and emits structured results for downstream consumers.
- **remediation-engine**: Receives anomaly events, performs root cause analysis (RCA) to classify failure modes, selects the appropriate remediation action (restart, scale, invoke Lambda), executes it, and records MTTD/MTTR telemetry.

## Architecture Diagram

```
                        ┌─────────────┐
                        │  Internet   │
                        └──────┬──────┘
                               │ HTTPS
                        ┌──────▼──────┐
                        │  AWS ALB    │
                        │  (Ingress)  │
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              │                                  │
   ┌──────────▼──────────┐           ┌──────────▼──────────┐
   │  anomaly-detector   │           │  remediation-engine │
   │  (FastAPI :8000)    │──────────►│  (FastAPI :8001)    │
   │  IsolationForest    │ anomaly   │  RCA engine         │
   │  + LSTM             │ events    │  + action handler   │
   └──────────┬──────────┘           └──────────┬──────────┘
              │                                  │
   ┌──────────▼──────────────────────────────────▼──────────┐
   │                   Shared Dependencies                    │
   │                                                          │
   │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │
   │  │ PostgreSQL │  │ Prometheus │  │  AWS Lambda fns    │ │
   │  │ RDS        │  │ :9090      │  │  (4 functions)     │ │
   │  └────────────┘  └────────────┘  └────────────────────┘ │
   │                                                          │
   │  ┌──────────────────────────────────────────────────┐   │
   │  │           Amazon CloudWatch                      │   │
   │  │  Alarms → SNS → Lambda alert-processor           │   │
   │  └──────────────────────────────────────────────────┘   │
   └──────────────────────────────────────────────────────────┘
```

## Component Descriptions

### anomaly-detector
Runs a dual-model anomaly detection pipeline:
- **IsolationForest**: Unsupervised statistical model that isolates outliers in the metric feature space. Low isolation score = anomaly.
- **LSTM**: Sequence model trained on historical metric windows to detect temporal anomalies (sudden shifts, trend breaks). Returns a reconstruction error score.

Both scores are ensembled into a final `anomaly_score` (0-1). Severity is bucketed: LOW (<0.4), MEDIUM (0.4-0.7), HIGH (0.7-0.9), CRITICAL (>0.9).

### remediation-engine
Receives anomaly payloads and runs a two-phase pipeline:
1. **RCA**: Classifies the root cause (CPU_SATURATION, MEMORY_PRESSURE, HIGH_ERROR_RATE, LATENCY_SPIKE, RESOURCE_EXHAUSTION) from the metric pattern, with a confidence score.
2. **Action handler**: Executes the recommended action — pod restart, horizontal scale-out, Lambda invocation, or circuit-breaker trip. All actions are idempotent and support DRY_RUN mode.

### Lambda Functions
| Function | Trigger | Purpose |
|---|---|---|
| alert-processor | CloudWatch SNS | Parses alarm payloads, enriches with tags, forwards to remediation-engine |
| auto-scaler | CloudWatch alarm (CPU/memory) | Adjusts EKS node group desired capacity |
| instance-restarter | CloudWatch alarm (status check) | Restarts failed EC2 instances or EKS pods |
| metrics-collector | EventBridge schedule (1 min) | Polls CloudWatch metrics, pushes to anomaly-detector /analyze |

### CloudWatch Alarms
Composite alarm fires when ≥2 of: CPU >80%, memory >85%, error rate >5%, latency p99 >2s. Sends to SNS topic → Lambda alert-processor.

## Data Flow

```
1. metrics-collector Lambda polls CloudWatch every 60 s
2. POSTs metric snapshot to anomaly-detector /analyze
3. anomaly-detector returns score + severity
4. If is_anomaly=true: POST to remediation-engine /remediate
5. remediation-engine runs RCA, executes action, records incident
6. Prometheus scrapes /metrics on both services
7. Grafana visualises dashboards from Prometheus
8. CloudWatch alarms (parallel path) → SNS → alert-processor Lambda → /remediate
```

## AWS Services

| Service | Role |
|---|---|
| EKS | Hosts both FastAPI services as K8s Deployments |
| RDS PostgreSQL | Persistent incident log storage |
| Lambda | Lightweight glue functions for CloudWatch integration |
| CloudWatch | Metrics ingestion, alarm evaluation, log aggregation |
| SNS | Fan-out alarm notifications to Lambda |
| Secrets Manager | Stores RDS credentials; pulled via ESO |
| ECR | Container image registry |
| ALB | L7 load balancer, TLS termination, path routing |
| IAM/IRSA | Pod-level AWS permissions without static keys |
| VPC | Network isolation, private subnets for EKS nodes + RDS |

## Security

- **IRSA**: Each K8s ServiceAccount is bound to a scoped IAM role via OIDC — no static AWS keys in pods.
- **External Secrets Operator**: Secrets Manager credentials are synced into K8s Secrets at runtime; no plaintext secrets in Git.
- **NetworkPolicy**: Ingress restricted per service; cross-namespace traffic denied by default.
- **IMDSv2**: All EKS nodes use `HttpTokens=required` in the launch template.
- **Encrypted storage**: EBS volumes (gp3, encrypted) and RDS storage encrypted at rest.
- **VPC flow logs**: Enabled for audit trail of all VPC traffic.
- **GitHub Actions OIDC**: CI/CD uses short-lived OIDC tokens — no long-lived AWS access keys in GitHub Secrets.

## EKS Configuration

- Kubernetes version: 1.29
- Managed node group: t3.medium, 1-5 nodes, cluster autoscaler enabled
- OIDC provider: created by Terraform, used for IRSA
- Control plane logging: api, audit, authenticator, controllerManager, scheduler → CloudWatch
- HPA: CPU 60% target, min 2 / max 8 replicas per service
- PDB: minAvailable 1 for both services
