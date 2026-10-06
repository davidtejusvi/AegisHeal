# AegisHeal — API Reference

## anomaly-detector (port 8000)

### GET /health
Returns service status and model training state.

**Response:**
```json
{"status": "ok", "model_trained": "True"}
```

**Example:**
```bash
curl http://localhost:8000/health
```

---

### GET /metrics
Prometheus-format metrics for scraping.

**Response:** `text/plain; version=0.0.4` (Prometheus exposition format)

**Example:**
```bash
curl http://localhost:8000/metrics
```

---

### POST /analyze
Score a metric snapshot for anomalies.

**Request:**
```json
{
  "service": "my-service",
  "metrics": {
    "cpu_utilization": 45.2,
    "memory_utilization": 62.1,
    "request_count": 120.0,
    "error_rate": 0.02,
    "latency_p99": 0.45
  }
}
```

**Response:**
```json
{
  "service": "my-service",
  "timestamp": "2024-01-15T10:30:00+00:00",
  "anomaly_score": 0.23,
  "severity": "LOW",
  "confidence": 0.87,
  "isolation_score": 0.21,
  "lstm_score": 0.25,
  "is_anomaly": false,
  "details": {}
}
```

| Field | Type | Description |
|---|---|---|
| anomaly_score | float [0-1] | Ensembled anomaly score; higher = more anomalous |
| severity | enum | LOW / MEDIUM / HIGH / CRITICAL |
| is_anomaly | bool | True if score exceeds threshold |
| isolation_score | float | IsolationForest raw score |
| lstm_score | float | LSTM reconstruction error score |

**Example:**
```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"service":"web","metrics":{"cpu_utilization":45.2,"memory_utilization":62.1,"request_count":120,"error_rate":0.02,"latency_p99":0.45}}'
```

---

### POST /train
Retrain the model on new historical data.

**Request:**
```json
{
  "service": "my-service",
  "history": [
    {"cpu_utilization": 40.0, "memory_utilization": 58.0, "request_count": 100.0, "error_rate": 0.01, "latency_p99": 0.3},
    "... (minimum 21 samples required)"
  ]
}
```

**Response:**
```json
{"status": "trained", "samples": "50"}
```

**Example:**
```bash
curl -X POST http://localhost:8000/train \
  -H 'Content-Type: application/json' \
  -d '{"service":"web","history":[{"cpu_utilization":40,"memory_utilization":58,"request_count":100,"error_rate":0.01,"latency_p99":0.3}]}'
```

---

### GET /anomalies
Return recent anomaly detection history.

**Query params:** `limit` (int, default 50, max 500)

**Response:** Array of AnomalyResponse objects (same schema as /analyze response).

**Example:**
```bash
curl 'http://localhost:8000/anomalies?limit=10'
```

---

## remediation-engine (port 8001)

### GET /health
Returns service status and dry-run mode.

**Response:**
```json
{"status": "ok", "dry_run": "False"}
```

**Example:**
```bash
curl http://localhost:8001/health
```

---

### GET /metrics
Prometheus-format metrics for scraping.

**Example:**
```bash
curl http://localhost:8001/metrics
```

---

### POST /remediate
Trigger root cause analysis and execute remediation.

**Request:**
```json
{
  "service": "anomaly-detector",
  "anomaly_score": 0.85,
  "severity": "HIGH",
  "metrics": {
    "cpu_utilization": 95.0,
    "memory_utilization": 55.0,
    "request_count": 80.0,
    "error_rate": 0.01,
    "latency_p99": 0.4
  },
  "detected_at": "2024-01-15T10:30:00+00:00",
  "context": {}
}
```

**Response:**
```json
{
  "incident_id": "a1b2c3d4",
  "service": "anomaly-detector",
  "anomaly_score": 0.85,
  "severity": "HIGH",
  "detected_at": "2024-01-15T10:30:00+00:00",
  "resolved_at": "2024-01-15T10:30:05+00:00",
  "mttr_seconds": 5.0,
  "auto_resolved": true,
  "root_cause": "CPU_SATURATION",
  "rca_confidence": 0.92,
  "evidence": [],
  "actions_taken": [
    {"action": "scale_out", "status": "success", "message": "Scaled deployment", "duration": 2.1}
  ]
}
```

**Example:**
```bash
curl -X POST http://localhost:8001/remediate \
  -H 'Content-Type: application/json' \
  -d '{"service":"web","anomaly_score":0.85,"severity":"HIGH","metrics":{"cpu_utilization":95,"memory_utilization":55,"request_count":80,"error_rate":0.01,"latency_p99":0.4}}'
```

---

### GET /incidents
Return recent incident history with MTTD/MTTR.

**Query params:** `limit` (int, default 50, max 1000)

**Response:** Array of incident objects (same schema as /remediate response).

**Example:**
```bash
curl 'http://localhost:8001/incidents?limit=20'
```

---

### GET /stats
Return aggregated remediation statistics.

**Response:**
```json
{
  "total_incidents": 42,
  "auto_resolved": 38,
  "auto_resolution_rate_pct": 90.5,
  "avg_mttr_seconds": 12.3,
  "downtime_prevented_minutes": 234.7,
  "root_cause_breakdown": {
    "CPU_SATURATION": 18,
    "MEMORY_PRESSURE": 12,
    "HIGH_ERROR_RATE": 8,
    "LATENCY_SPIKE": 4
  }
}
```

**Example:**
```bash
curl http://localhost:8001/stats
```

---

### POST /simulate
Run a remediation dry-run with synthetic failure metrics.

**Request:**
```json
{
  "service": "anomaly-detector",
  "failure_type": "cpu_spike"
}
```

`failure_type` options: `cpu_spike`, `memory_pressure`, `high_error_rate`, `latency_spike`

**Response:**
```json
{
  "mode": "simulation",
  "failure_type": "cpu_spike",
  "service": "anomaly-detector",
  "metrics_used": {"cpu_utilization": 95.0, "...": "..."},
  "root_cause": "CPU_SATURATION",
  "confidence": 0.92,
  "evidence": [],
  "would_execute": ["scale_out", "restart_pod"]
}
```

**Example:**
```bash
curl -X POST http://localhost:8001/simulate \
  -H 'Content-Type: application/json' \
  -d '{"service":"my-svc","failure_type":"memory_pressure"}'
```

---

## Common Error Codes

| HTTP Status | Meaning | Resolution |
|---|---|---|
| 422 Unprocessable Entity | Validation error (e.g. fewer than 21 training samples, anomaly_score out of 0-1 range) | Check request schema and field constraints |
| 500 Internal Server Error | Unexpected server error | Check pod logs: `kubectl logs -l app=<service> -n monitoring-platform` |
| 503 Service Unavailable | Pod not ready (startup, OOM restart) | Check `kubectl get pods -n monitoring-platform` and liveness probe status |
