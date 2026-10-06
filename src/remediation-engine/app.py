"""
Remediation Engine — FastAPI service
Endpoints:
  GET  /health
  GET  /metrics        (Prometheus format)
  POST /remediate      (run RCA + execute fix)
  GET  /incidents      (history with MTTD/MTTR)
  GET  /stats          (research metrics summary)
  POST /simulate       (dry-run chaos test)
"""
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from config import config
from root_cause_analyzer import RootCauseAnalyzer, RCAResult
from remediation_handler import RemediationHandler, ActionStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Remediation Engine",
    description="Automated root cause analysis and remediation service",
    version="1.0.0",
)

analyzer  = RootCauseAnalyzer()
handler   = RemediationHandler()

# Rolling incident log (last 1000)
_incidents: deque[dict[str, Any]] = deque(maxlen=1000)

# ── Prometheus metrics ─────────────────────────────────────────────────────────
incidents_total      = Counter("remediation_incidents_total", "Total incidents processed")
auto_resolved_total  = Counter("remediation_auto_resolved_total", "Incidents auto-resolved")
failed_actions_total = Counter("remediation_failed_actions_total", "Failed remediation actions")
mttd_histogram       = Histogram("remediation_mttd_seconds", "Mean time to detect (seconds)")
mttr_histogram       = Histogram("remediation_mttr_seconds", "Mean time to recover (seconds)")
active_incidents     = Gauge("remediation_active_incidents", "Currently open incidents")


# ── Request / response models ──────────────────────────────────────────────────

class RemediateRequest(BaseModel):
    service:       str
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    severity:      str
    metrics:       dict[str, float]
    detected_at:   str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    context:       dict[str, Any] = Field(default_factory=dict)


class SimulateRequest(BaseModel):
    service:       str
    failure_type:  str = Field(
        ...,
        description="One of: cpu_spike, memory_pressure, high_error_rate, latency_spike",
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "dry_run": str(config.DRY_RUN)}


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/remediate")
def remediate(req: RemediateRequest) -> dict[str, Any]:
    incident_id = str(uuid.uuid4())[:8]
    incidents_total.inc()
    active_incidents.inc()

    # 1 — Root cause analysis
    rca: RCAResult = analyzer.analyze(req.metrics, req.anomaly_score, req.service)

    # 2 — Execute recommended actions
    actions = handler.execute(
        service=req.service,
        recommended_actions=rca.primary.recommended_actions,
        context=req.context,
    )

    # 3 — Determine outcome
    any_success = any(a.status == ActionStatus.SUCCESS for a in actions)
    resolved_at = datetime.now(timezone.utc).isoformat()

    if any_success:
        auto_resolved_total.inc()
    else:
        failed_actions_total.inc()

    active_incidents.dec()

    # 4 — Record MTTR
    try:
        detected_dt = datetime.fromisoformat(req.detected_at)
        resolved_dt = datetime.fromisoformat(resolved_at)
        mttr_s = (resolved_dt - detected_dt).total_seconds()
        mttr_histogram.observe(mttr_s)
    except ValueError:
        mttr_s = 0.0

    incident = {
        "incident_id":   incident_id,
        "service":       req.service,
        "anomaly_score": req.anomaly_score,
        "severity":      req.severity,
        "detected_at":   req.detected_at,
        "resolved_at":   resolved_at,
        "mttr_seconds":  round(mttr_s, 1),
        "auto_resolved": any_success,
        "root_cause":    rca.primary.cause.value,
        "rca_confidence": rca.primary.confidence,
        "evidence":      rca.all_evidence,
        "actions_taken": [
            {
                "action":   a.action,
                "status":   a.status.value,
                "message":  a.message,
                "duration": a.duration_s,
            }
            for a in actions
        ],
    }
    _incidents.appendleft(incident)
    logger.info("Incident %s resolved=%s root_cause=%s", incident_id, any_success, rca.primary.cause.value)

    return incident


@app.get("/incidents")
def incidents(limit: int = 50) -> list[dict]:
    return list(_incidents)[:limit]


@app.get("/stats")
def stats() -> dict[str, Any]:
    all_inc = list(_incidents)
    if not all_inc:
        return {"message": "No incidents recorded yet"}

    auto_resolved   = [i for i in all_inc if i["auto_resolved"]]
    mttr_values     = [i["mttr_seconds"] for i in all_inc if i["mttr_seconds"] > 0]

    avg_mttr = round(sum(mttr_values) / len(mttr_values), 1) if mttr_values else 0.0
    downtime_prevented_min = round(sum(
        max(0, 600 - i["mttr_seconds"]) for i in auto_resolved
    ) / 60, 1)

    return {
        "total_incidents":          len(all_inc),
        "auto_resolved":            len(auto_resolved),
        "auto_resolution_rate_pct": round(len(auto_resolved) / len(all_inc) * 100, 1),
        "avg_mttr_seconds":         avg_mttr,
        "downtime_prevented_minutes": downtime_prevented_min,
        "root_cause_breakdown":     _cause_breakdown(all_inc),
    }


@app.post("/simulate")
def simulate(req: SimulateRequest) -> dict[str, Any]:
    """Runs a remediation cycle in dry-run mode with synthetic failure metrics."""
    synthetic_metrics: dict[str, dict[str, float]] = {
        "cpu_spike": {
            "cpu_utilization": 95.0, "memory_utilization": 55.0,
            "request_count": 80.0,  "error_rate": 0.01,
            "latency_p99": 0.4,
        },
        "memory_pressure": {
            "cpu_utilization": 40.0, "memory_utilization": 94.0,
            "request_count": 120.0, "error_rate": 0.02,
            "latency_p99": 0.6,
        },
        "high_error_rate": {
            "cpu_utilization": 50.0, "memory_utilization": 60.0,
            "request_count": 200.0, "error_rate": 0.18,
            "latency_p99": 1.2,
        },
        "latency_spike": {
            "cpu_utilization": 55.0, "memory_utilization": 62.0,
            "request_count": 150.0, "error_rate": 0.03,
            "latency_p99": 8.5,
        },
    }
    metrics = synthetic_metrics.get(req.failure_type, synthetic_metrics["cpu_spike"])
    rca = analyzer.analyze(metrics, 0.85, req.service)

    return {
        "mode":             "simulation",
        "failure_type":     req.failure_type,
        "service":          req.service,
        "metrics_used":     metrics,
        "root_cause":       rca.primary.cause.value,
        "confidence":       rca.primary.confidence,
        "evidence":         rca.all_evidence,
        "would_execute":    rca.primary.recommended_actions,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cause_breakdown(incidents: list[dict]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for inc in incidents:
        cause = inc.get("root_cause", "unknown")
        breakdown[cause] = breakdown.get(cause, 0) + 1
    return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))
