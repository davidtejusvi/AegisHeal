"""
Anomaly Detector — FastAPI service
Endpoints:
  GET  /health
  GET  /metrics        (Prometheus format)
  POST /analyze        (score a metrics snapshot)
  POST /train          (retrain model on new data)
  GET  /anomalies      (recent anomaly history)
"""
import logging
from datetime import datetime, timezone
from collections import deque
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from config import config
from detector import AnomalyDetector, AnomalyResult, Severity
from metrics_collector import MetricsCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Anomaly Detector",
    description="AI-powered metric anomaly detection service",
    version="1.0.0",
)

# ── Singletons ─────────────────────────────────────────────────────────────────
detector  = AnomalyDetector()
collector = MetricsCollector()

# Rolling history of the last 500 anomaly results
_anomaly_history: deque[dict[str, Any]] = deque(maxlen=500)

# ── Prometheus counters ────────────────────────────────────────────────────────
analyze_requests  = Counter("anomaly_analyze_requests_total", "Total /analyze calls")
anomalies_found   = Counter("anomaly_detected_total", "Total anomalies detected", ["severity"])
analyze_latency   = Histogram("anomaly_analyze_duration_seconds", "Time spent in /analyze")


# ── Request / response models ──────────────────────────────────────────────────

class MetricsPayload(BaseModel):
    service: str = Field(..., description="Service name being analysed")
    metrics: dict[str, float] = Field(
        ...,
        description="Key/value metric snapshot (cpu_utilization, error_rate, …)",
        example={
            "cpu_utilization":    45.2,
            "memory_utilization": 62.1,
            "request_count":      120.0,
            "error_rate":         0.02,
            "latency_p99":        0.45,
        },
    )


class TrainPayload(BaseModel):
    service: str
    history: list[dict[str, float]] = Field(
        ..., description="List of metric snapshots used for training"
    )


class AnomalyResponse(BaseModel):
    service:         str
    timestamp:       str
    anomaly_score:   float
    severity:        Severity
    confidence:      float
    isolation_score: float
    lstm_score:      float
    is_anomaly:      bool
    details:         dict


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_trained": str(detector._trained)}


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/analyze", response_model=AnomalyResponse)
def analyze(payload: MetricsPayload) -> AnomalyResponse:
    analyze_requests.inc()

    with analyze_latency.time():
        result: AnomalyResult = detector.detect(payload.metrics)

    ts = datetime.now(timezone.utc).isoformat()

    if result.is_anomaly:
        anomalies_found.labels(severity=result.severity.value).inc()

    record = {
        "service":         payload.service,
        "timestamp":       ts,
        "anomaly_score":   result.anomaly_score,
        "severity":        result.severity,
        "confidence":      result.confidence,
        "isolation_score": result.isolation_score,
        "lstm_score":      result.lstm_score,
        "is_anomaly":      result.is_anomaly,
        "details":         result.details,
    }
    _anomaly_history.appendleft(record)

    return AnomalyResponse(**record)


@app.post("/train")
def train(payload: TrainPayload) -> dict[str, str]:
    if len(payload.history) < 21:
        raise HTTPException(
            status_code=422,
            detail="At least 21 samples required for training",
        )
    detector.train(payload.history)
    return {"status": "trained", "samples": str(len(payload.history))}


@app.get("/anomalies")
def anomalies(limit: int = 50) -> list[dict]:
    return list(_anomaly_history)[:limit]
