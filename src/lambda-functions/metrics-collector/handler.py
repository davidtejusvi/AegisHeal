"""
metrics-collector Lambda
-------------------------
Triggered by: EventBridge rule (every 1 minute)
Purpose:      Collect CloudWatch metrics for all monitored services,
              store them in RDS for time-series analysis, and trigger
              a batch anomaly analysis pass.
"""
import json
import logging
import os
import boto3
import psycopg2
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION  = os.environ.get("AWS_REGION",  "us-east-1")
DB_HOST     = os.environ.get("DB_HOST",     "localhost")
DB_PORT     = int(os.environ.get("DB_PORT", "5432"))
DB_NAME     = os.environ.get("DB_NAME",     "aimonitor")
DB_USER     = os.environ.get("DB_USER",     "aimonitor")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

# Comma-separated list of services to monitor
MONITORED_SERVICES = os.environ.get(
    "MONITORED_SERVICES", "api-service,worker-service,web-frontend"
).split(",")

cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)

# Metric definitions: (namespace, metric_name, stat, friendly_name)
METRIC_DEFINITIONS = [
    ("AWS/EC2",             "CPUUtilization",           "Average", "cpu_utilization"),
    ("AWS/EC2",             "NetworkIn",                "Sum",     "network_in"),
    ("AWS/EC2",             "NetworkOut",               "Sum",     "network_out"),
    ("AWS/ApplicationELB",  "TargetResponseTime",       "p99",     "latency_p99"),
    ("AWS/ApplicationELB",  "HTTPCode_Target_5XX_Count","Sum",     "error_count"),
    ("AWS/ApplicationELB",  "RequestCount",             "Sum",     "request_count"),
    ("AWS/RDS",             "CPUUtilization",           "Average", "rds_cpu"),
    ("AWS/RDS",             "FreeStorageSpace",         "Average", "rds_free_storage"),
]


# ── Database ───────────────────────────────────────────────────────────────────

def _get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        connect_timeout=5,
    )


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id          SERIAL PRIMARY KEY,
                service     VARCHAR(100) NOT NULL,
                metric_name VARCHAR(100) NOT NULL,
                value       DOUBLE PRECISION NOT NULL,
                collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_metrics_service_time
                ON metrics (service, collected_at DESC);
        """)
    conn.commit()


def _store_metrics(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO metrics (service, metric_name, value, collected_at)
            VALUES (%(service)s, %(metric_name)s, %(value)s, %(collected_at)s)
            """,
            rows,
        )
    conn.commit()
    return len(rows)


# ── CloudWatch collection ──────────────────────────────────────────────────────

def _collect_metrics_for_service(service: str) -> list[dict]:
    now   = datetime.now(timezone.utc)
    start = now - timedelta(minutes=2)   # last 2-minute window

    queries = [
        {
            "Id": f"m{idx}",
            "MetricStat": {
                "Metric": {
                    "Namespace":  ns,
                    "MetricName": metric,
                    "Dimensions": [],
                },
                "Period": 60,
                "Stat":   stat,
            },
            "Label":      label,
            "ReturnData": True,
        }
        for idx, (ns, metric, stat, label) in enumerate(METRIC_DEFINITIONS)
    ]

    try:
        resp = cloudwatch.get_metric_data(
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=now,
        )
    except ClientError as exc:
        logger.error("CloudWatch error for %s: %s", service, exc)
        return []

    rows: list[dict] = []
    ts_str = now.isoformat()

    for result in resp.get("MetricDataResults", []):
        if result["Values"]:
            rows.append({
                "service":      service,
                "metric_name":  result["Label"],
                "value":        float(result["Values"][-1]),
                "collected_at": ts_str,
            })

    logger.info("Collected %d metric points for '%s'", len(rows), service)
    return rows


# ── Handler ────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    logger.info("metrics-collector triggered: %s", json.dumps(event))

    all_rows: list[dict] = []

    for service in MONITORED_SERVICES:
        rows = _collect_metrics_for_service(service.strip())
        all_rows.extend(rows)

    stored = 0
    db_error = None

    try:
        conn = _get_db_connection()
        _ensure_table(conn)
        stored = _store_metrics(conn, all_rows)
        conn.close()
        logger.info("Stored %d metric rows in RDS", stored)
    except Exception as exc:
        db_error = str(exc)
        logger.error("DB error: %s", exc)

    summary = {
        "services_polled": len(MONITORED_SERVICES),
        "metrics_collected": len(all_rows),
        "metrics_stored":  stored,
        "db_error":        db_error,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }

    return {"statusCode": 200, "body": summary}
