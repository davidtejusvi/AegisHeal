"""
Root cause analysis — maps anomaly patterns to probable causes
using rule-based matching and confidence scoring.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RootCause(str, Enum):
    COMPUTE_SATURATION   = "compute_saturation"
    MEMORY_LEAK          = "memory_leak"
    TRAFFIC_SPIKE        = "traffic_spike"
    RUNAWAY_PROCESS      = "runaway_process"
    HIGH_ERROR_RATE      = "high_error_rate"
    SLOW_DEPENDENCY      = "slow_dependency"
    DISK_PRESSURE        = "disk_pressure"
    NETWORK_ISSUE        = "network_issue"
    DEPLOYMENT_REGRESSION = "deployment_regression"
    UNKNOWN              = "unknown"


@dataclass
class RootCauseHypothesis:
    cause:       RootCause
    confidence:  float          # 0.0 – 1.0
    evidence:    list[str]      # human-readable evidence strings
    recommended_actions: list[str] = field(default_factory=list)


@dataclass
class RCAResult:
    primary:      RootCauseHypothesis
    alternatives: list[RootCauseHypothesis]
    all_evidence: list[str]


# ── Rule definitions ───────────────────────────────────────────────────────────
# Each rule returns a confidence score (0.0–1.0) and the evidence it matched.

def _rule_compute_saturation(metrics: dict[str, float]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    cpu = metrics.get("cpu_utilization", 0.0)
    if cpu > 90:
        evidence.append(f"CPU at {cpu:.1f}% (critical)")
        score += 0.7
    elif cpu > 80:
        evidence.append(f"CPU at {cpu:.1f}% (high)")
        score += 0.4
    if metrics.get("request_count", 0) > 1000:
        evidence.append("Request count very high")
        score += 0.2
    return min(score, 1.0), evidence


def _rule_memory_leak(metrics: dict[str, float]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    mem = metrics.get("memory_utilization", 0.0)
    if mem > 90:
        evidence.append(f"Memory at {mem:.1f}% (critical)")
        score += 0.75
    elif mem > 80:
        evidence.append(f"Memory at {mem:.1f}% (high)")
        score += 0.4
    cpu = metrics.get("cpu_utilization", 0.0)
    if mem > 80 and cpu < 50:
        evidence.append("High memory with low CPU — likely leak, not load")
        score += 0.2
    return min(score, 1.0), evidence


def _rule_traffic_spike(metrics: dict[str, float]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    rps = metrics.get("request_count", 0.0)
    if rps > 500:
        evidence.append(f"Request rate at {rps:.0f} rps (spike)")
        score += 0.6
    cpu = metrics.get("cpu_utilization", 0.0)
    if rps > 500 and cpu > 70:
        evidence.append("Both request rate and CPU elevated together")
        score += 0.25
    return min(score, 1.0), evidence


def _rule_runaway_process(metrics: dict[str, float]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    cpu = metrics.get("cpu_utilization", 0.0)
    rps = metrics.get("request_count", 0.0)
    # High CPU with low traffic = something spinning in the background
    if cpu > 85 and rps < 100:
        evidence.append(f"CPU {cpu:.1f}% with only {rps:.0f} rps — runaway process suspected")
        score += 0.75
    return min(score, 1.0), evidence


def _rule_high_error_rate(metrics: dict[str, float]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    err = metrics.get("error_rate", 0.0)
    if err > 0.1:
        evidence.append(f"Error rate at {err*100:.1f}% (critical)")
        score += 0.8
    elif err > 0.05:
        evidence.append(f"Error rate at {err*100:.1f}% (elevated)")
        score += 0.5
    return min(score, 1.0), evidence


def _rule_slow_dependency(metrics: dict[str, float]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    p99 = metrics.get("latency_p99", 0.0)
    if p99 > 5.0:
        evidence.append(f"p99 latency at {p99:.2f}s (very slow)")
        score += 0.7
    elif p99 > 2.0:
        evidence.append(f"p99 latency at {p99:.2f}s (slow)")
        score += 0.4
    err = metrics.get("error_rate", 0.0)
    if p99 > 2.0 and err < 0.05:
        evidence.append("Latency high but errors low — points to slow upstream dependency")
        score += 0.2
    return min(score, 1.0), evidence


def _rule_disk_pressure(metrics: dict[str, float]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    disk = metrics.get("disk_io", 0.0)
    if disk > 90:
        evidence.append(f"Disk I/O at {disk:.1f}% (saturated)")
        score += 0.8
    elif disk > 70:
        evidence.append(f"Disk I/O at {disk:.1f}% (high)")
        score += 0.4
    return min(score, 1.0), evidence


def _rule_network_issue(metrics: dict[str, float]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    net_in  = metrics.get("network_in", 0.0)
    net_out = metrics.get("network_out", 0.0)
    if net_in > 1_000_000_000 or net_out > 1_000_000_000:
        evidence.append("Network throughput extremely high (possible saturation or DDoS)")
        score += 0.6
    p99 = metrics.get("latency_p99", 0.0)
    err = metrics.get("error_rate", 0.0)
    if p99 > 2.0 and err > 0.05 and net_out < 1_000:
        evidence.append("High latency + errors with low outbound traffic — network issue likely")
        score += 0.4
    return min(score, 1.0), evidence


# Map each root cause to its rule function and recommended actions
_RULES: list[tuple[RootCause, Any, list[str]]] = [
    (
        RootCause.COMPUTE_SATURATION,
        _rule_compute_saturation,
        ["scale_out_kubernetes", "trigger_auto_scaler"],
    ),
    (
        RootCause.MEMORY_LEAK,
        _rule_memory_leak,
        ["restart_pods", "trigger_instance_restarter"],
    ),
    (
        RootCause.TRAFFIC_SPIKE,
        _rule_traffic_spike,
        ["trigger_auto_scaler", "scale_out_kubernetes"],
    ),
    (
        RootCause.RUNAWAY_PROCESS,
        _rule_runaway_process,
        ["restart_pods", "ssm_restart_service"],
    ),
    (
        RootCause.HIGH_ERROR_RATE,
        _rule_high_error_rate,
        ["rollback_deployment", "ssm_restart_service"],
    ),
    (
        RootCause.SLOW_DEPENDENCY,
        _rule_slow_dependency,
        ["ssm_clear_cache", "scale_out_kubernetes"],
    ),
    (
        RootCause.DISK_PRESSURE,
        _rule_disk_pressure,
        ["ssm_clear_cache"],
    ),
    (
        RootCause.NETWORK_ISSUE,
        _rule_network_issue,
        ["trigger_auto_scaler"],
    ),
]


# ── Analyser ───────────────────────────────────────────────────────────────────

class RootCauseAnalyzer:

    def analyze(
        self,
        metrics: dict[str, float],
        anomaly_score: float,
        service: str,
    ) -> RCAResult:
        hypotheses: list[RootCauseHypothesis] = []
        all_evidence: list[str] = []

        for cause, rule_fn, actions in _RULES:
            confidence, evidence = rule_fn(metrics)
            if confidence > 0.0:
                hypotheses.append(
                    RootCauseHypothesis(
                        cause=cause,
                        confidence=round(confidence, 3),
                        evidence=evidence,
                        recommended_actions=actions,
                    )
                )
                all_evidence.extend(evidence)

        # Sort by confidence descending
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)

        if not hypotheses:
            primary = RootCauseHypothesis(
                cause=RootCause.UNKNOWN,
                confidence=0.0,
                evidence=["No matching rule found"],
                recommended_actions=["ssm_restart_service"],
            )
            alternatives = []
        else:
            primary      = hypotheses[0]
            alternatives = hypotheses[1:3]   # top 2 alternatives

        logger.info(
            "RCA for '%s': primary=%s (%.2f), alternatives=%s",
            service,
            primary.cause.value,
            primary.confidence,
            [h.cause.value for h in alternatives],
        )

        return RCAResult(
            primary=primary,
            alternatives=alternatives,
            all_evidence=all_evidence,
        )
