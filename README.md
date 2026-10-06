# AWS AI-Powered Monitoring & Automated Remediation Platform

## Research Question
> Can AI-based anomaly detection and automated remediation reduce cloud downtime and operational effort compared with traditional DevOps monitoring?

---

## What This Project Does

This platform monitors AWS-hosted applications, detects failures using AI/ML, identifies root causes automatically, and triggers remediation — all without manual intervention.

| Capability | Technology |
|---|---|
| Metrics collection | CloudWatch + Prometheus |
| Anomaly detection | Python (Isolation Forest + LSTM) |
| Root cause analysis | Rule-based + ML correlation |
| Automated remediation | Lambda + SSM + Kubernetes |
| Infrastructure | Terraform |
| CI/CD | GitHub Actions |
| Visualization | Grafana + React dashboard |

---

## Project Structure

```
.
├── terraform/          # All AWS infrastructure as code
├── src/                # Application source code
│   ├── anomaly-detector/     # AI/ML detection service
│   ├── remediation-engine/   # Automated fix orchestrator
│   ├── lambda-functions/     # Event-driven Lambda handlers
│   └── dashboard/            # React monitoring dashboard
├── k8s/                # Kubernetes manifests
├── monitoring/         # CloudWatch + Prometheus config
├── .github/workflows/  # CI/CD pipelines
├── scripts/            # Helper scripts
└── docs/               # Architecture and research docs
```

---

## Key Metrics Being Measured

- **MTTD** — Mean Time to Detect (target: < 2 min)
- **MTTR** — Mean Time to Recover (target: < 10 min)
- **Auto-remediation rate** — % of incidents resolved without human input
- **False positive rate** — AI alert accuracy
- **Downtime prevented** — Estimated hours saved
- **Cost savings** — Reduced operational overhead

---

## Getting Started

> Prerequisites: AWS CLI, Terraform >= 1.6, kubectl, Docker, Node.js 18+

Steps will be added here as each phase is built out.

---

## Build Phases

- [x] Phase 1 — Project structure & documentation
- [ ] Phase 2 — Terraform: VPC + networking
- [ ] Phase 3 — Terraform: EKS + IAM
- [ ] Phase 4 — CloudWatch monitoring + alarms
- [ ] Phase 5 — Anomaly detection service (Python)
- [ ] Phase 6 — Remediation engine (Python)
- [ ] Phase 7 — Lambda functions
- [ ] Phase 8 — GitHub Actions CI/CD
- [ ] Phase 9 — React dashboard
