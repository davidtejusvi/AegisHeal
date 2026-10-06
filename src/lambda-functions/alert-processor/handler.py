"""
alert-processor Lambda
-----------------------
Triggered by: CloudWatch Alarm → SNS → Lambda
Purpose:      Enrich the alert with live metrics, call the anomaly detector,
              and route to the remediation engine if anomaly is confirmed.
"""
import json
import logging
import os
import boto3
import requests
from botocore.exceptions import ClientError
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION           = os.environ.get("AWS_REGION",           "us-east-1")
ANOMALY_DETECTOR_URL = os.environ.get("ANOMALY_DETECTOR_URL", "http://anomaly-detector:8000")
REMEDIATION_URL      = os.environ.get("REMEDIATION_URL",      "http://remediation-engine:8001")
SNS_TOPIC            = os.environ.get("SNS_ALERT_TOPIC_ARN",  "")
MIN_ANOMALY_SCORE    = float(os.environ.get("MIN_ANOMALY_SCORE", "0.5"))

cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
sns_client = boto3.client("sns",        region_name=AWS_REGION)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _notify(subject: str, message: str) -> None:
    if not SNS_TOPIC:
        return
    try:
        sns_client.publish(TopicArn=SNS_TOPIC, Subject=subject, Message=message)
    except ClientError as exc:
        logger.warning("SNS publish failed: %s", exc)


def _fetch_live_metrics(service: str) -> dict[str, float]:
    """Pull the most recent CloudWatch metrics for the service."""
    metrics: dict[str, float] = {}
    queries = [
        ("cpu_utilization",    "AWS/EC2",          "CPUUtilization",    "Average"),
        ("network_in",         "AWS/EC2",           "NetworkIn",         "Sum"),
        ("network_out",        "AWS/EC2",           "NetworkOut",        "Sum"),
        ("error_rate",         "AWS/ApplicationELB","HTTPCode_Target_5XX_Count", "Sum"),
        ("latency_p99",        "AWS/ApplicationELB","TargetResponseTime", "p99"),
    ]
    try:
        from datetime import timedelta
        now   = datetime.now(timezone.utc)
        start = now - timedelta(minutes=5)

        data_queries = [
            {
                "Id": q[0],
                "MetricStat": {
                    "Metric": {
                        "Namespace":  q[1],
                        "MetricName": q[2],
                        "Dimensions": [],
                    },
                    "Period": 300,
                    "Stat":   q[3],
                },
                "ReturnData": True,
            }
            for q in queries
        ]

        resp = cloudwatch.get_metric_data(
            MetricDataQueries=data_queries,
            StartTime=start,
            EndTime=now,
        )
        for result in resp.get("MetricDataResults", []):
            if result["Values"]:
                metrics[result["Id"]] = float(result["Values"][-1])
    except ClientError as exc:
        logger.warning("Could not fetch live metrics: %s", exc)

    # Defaults so the detector always gets a complete vector
    defaults = {
        "cpu_utilization": 0.0, "memory_utilization": 0.0,
        "request_count":   0.0, "error_rate":         0.0,
        "latency_p99":     0.0, "disk_io":            0.0,
        "network_in":      0.0, "network_out":        0.0,
    }
    return {**defaults, **metrics}


def _call_anomaly_detector(service: str, metrics: dict[str, float]) -> dict:
    try:
        resp = requests.post(
            f"{ANOMALY_DETECTOR_URL}/analyze",
            json={"service": service, "metrics": metrics},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("Anomaly detector call failed: %s", exc)
        return {}


def _call_remediation_engine(service: str, anomaly: dict, metrics: dict[str, float]) -> dict:
    try:
        resp = requests.post(
            f"{REMEDIATION_URL}/remediate",
            json={
                "service":       service,
                "anomaly_score": anomaly.get("anomaly_score", 0.0),
                "severity":      anomaly.get("severity", "UNKNOWN"),
                "metrics":       metrics,
                "detected_at":   datetime.now(timezone.utc).isoformat(),
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("Remediation engine call failed: %s", exc)
        return {}


# ── Handler ────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    logger.info("Event: %s", json.dumps(event))

    # Parse SNS message
    try:
        raw_message = event["Records"][0]["Sns"]["Message"]
        alarm_data  = json.loads(raw_message)
    except (KeyError, IndexError, json.JSONDecodeError):
        alarm_data  = event

    alarm_name  = alarm_data.get("AlarmName", "unknown-alarm")
    alarm_state = alarm_data.get("NewStateValue", "ALARM")
    service     = alarm_data.get("service", alarm_name.split("-")[0])

    logger.info("Processing alarm '%s' state=%s service=%s", alarm_name, alarm_state, service)

    # Only act on ALARM state
    if alarm_state != "ALARM":
        return {"statusCode": 200, "body": {"skipped": True, "reason": "not_in_alarm_state"}}

    # Step 1 — Fetch live metrics
    metrics = _fetch_live_metrics(service)
    logger.info("Live metrics: %s", metrics)

    # Step 2 — Anomaly detection
    anomaly = _call_anomaly_detector(service, metrics)
    score   = anomaly.get("anomaly_score", 0.0)
    logger.info("Anomaly score=%.3f severity=%s", score, anomaly.get("severity", "?"))

    result = {
        "alarm_name":    alarm_name,
        "service":       service,
        "metrics":       metrics,
        "anomaly_score": score,
        "severity":      anomaly.get("severity", "UNKNOWN"),
        "remediated":    False,
    }

    # Step 3 — Route to remediation if confirmed anomaly
    if score >= MIN_ANOMALY_SCORE:
        remediation = _call_remediation_engine(service, anomaly, metrics)
        result["remediated"]       = True
        result["remediation_id"]   = remediation.get("incident_id")
        result["root_cause"]       = remediation.get("root_cause")
        result["auto_resolved"]    = remediation.get("auto_resolved", False)

        _notify(
            subject=f"[AI-Monitor] Alert processed: {alarm_name} (score={score:.2f})",
            message=json.dumps(result, indent=2),
        )
    else:
        logger.info("Score %.3f below threshold %.3f — no remediation", score, MIN_ANOMALY_SCORE)

    return {"statusCode": 200, "body": result}
