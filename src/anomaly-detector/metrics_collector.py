"""
Pulls metrics from CloudWatch and Prometheus,
normalises them into a common schema.
"""
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import boto3
import requests
from botocore.exceptions import ClientError

from config import config

logger = logging.getLogger(__name__)

# ── Common schema ──────────────────────────────────────────────────────────────
MetricPoint = dict[str, Any]
# {
#   "service":     str,
#   "metric_name": str,
#   "value":       float,
#   "timestamp":   str  (ISO-8601),
#   "source":      "cloudwatch" | "prometheus",
# }


# ── CloudWatch collector ───────────────────────────────────────────────────────

class CloudWatchCollector:
    """Fetches metrics via the CloudWatch GetMetricData API."""

    METRIC_QUERIES = [
        {
            "Id":         "cpu",
            "MetricStat": {
                "Metric": {
                    "Namespace":  "AWS/EC2",
                    "MetricName": "CPUUtilization",
                    "Dimensions": [],
                },
                "Period": 60,
                "Stat":   "Average",
            },
            "Label": "cpu_utilization",
        },
        {
            "Id":         "network_in",
            "MetricStat": {
                "Metric": {
                    "Namespace":  "AWS/EC2",
                    "MetricName": "NetworkIn",
                    "Dimensions": [],
                },
                "Period": 60,
                "Stat":   "Sum",
            },
            "Label": "network_in",
        },
        {
            "Id":         "network_out",
            "MetricStat": {
                "Metric": {
                    "Namespace":  "AWS/EC2",
                    "MetricName": "NetworkOut",
                    "Dimensions": [],
                },
                "Period": 60,
                "Stat":   "Sum",
            },
            "Label": "network_out",
        },
    ]

    def __init__(self) -> None:
        self._client = boto3.client("cloudwatch", region_name=config.AWS_REGION)

    def collect(self, service: str) -> list[MetricPoint]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(seconds=config.METRICS_WINDOW_SECONDS)

        try:
            response = self._client.get_metric_data(
                MetricDataQueries=self.METRIC_QUERIES,
                StartTime=start,
                EndTime=now,
            )
        except ClientError as exc:
            logger.error("CloudWatch error: %s", exc)
            return []

        points: list[MetricPoint] = []
        for result in response.get("MetricDataResults", []):
            label = result["Label"]
            for ts, val in zip(result["Timestamps"], result["Values"]):
                points.append(
                    {
                        "service":     service,
                        "metric_name": label,
                        "value":       float(val),
                        "timestamp":   ts.isoformat(),
                        "source":      "cloudwatch",
                    }
                )
        return points


# ── Prometheus collector ───────────────────────────────────────────────────────

PROMETHEUS_QUERIES: dict[str, str] = {
    "request_count":    'sum(rate(http_requests_total[1m]))',
    "error_rate":       'sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))',
    "latency_p99":      'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[1m])) by (le))',
    "memory_utilization": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
    "disk_io":          'sum(rate(node_disk_io_time_seconds_total[1m])) * 100',
}


class PrometheusCollector:
    """Fetches metrics from the Prometheus HTTP API."""

    def __init__(self) -> None:
        self._base_url = config.PROMETHEUS_URL.rstrip("/")

    def collect(self, service: str) -> list[MetricPoint]:
        points: list[MetricPoint] = []
        end   = time.time()
        start = end - config.METRICS_WINDOW_SECONDS

        for metric_name, query in PROMETHEUS_QUERIES.items():
            try:
                resp = requests.get(
                    f"{self._base_url}/api/v1/query_range",
                    params={
                        "query": query,
                        "start": start,
                        "end":   end,
                        "step":  config.METRICS_RESOLUTION_SECONDS,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                logger.warning("Prometheus query failed (%s): %s", metric_name, exc)
                continue

            for result in data.get("data", {}).get("result", []):
                for ts_str, val_str in result.get("values", []):
                    try:
                        points.append(
                            {
                                "service":     service,
                                "metric_name": metric_name,
                                "value":       float(val_str),
                                "timestamp":   datetime.fromtimestamp(
                                    float(ts_str), tz=timezone.utc
                                ).isoformat(),
                                "source":      "prometheus",
                            }
                        )
                    except (ValueError, TypeError):
                        continue
        return points


# ── Unified collector ──────────────────────────────────────────────────────────

class MetricsCollector:
    """Aggregates CloudWatch + Prometheus into one normalised list."""

    def __init__(self) -> None:
        self._cw   = CloudWatchCollector()
        self._prom = PrometheusCollector()

    def collect_all(self, service: str) -> list[MetricPoint]:
        cw_points   = self._cw.collect(service)
        prom_points = self._prom.collect(service)
        all_points  = cw_points + prom_points
        logger.info(
            "Collected %d metrics for service '%s' (cw=%d prom=%d)",
            len(all_points), service, len(cw_points), len(prom_points),
        )
        return all_points

    def latest_values(self, service: str) -> dict[str, float]:
        """Return only the most recent value per metric name."""
        points = self.collect_all(service)
        latest: dict[str, MetricPoint] = {}
        for p in points:
            name = p["metric_name"]
            if name not in latest or p["timestamp"] > latest[name]["timestamp"]:
                latest[name] = p
        return {name: pt["value"] for name, pt in latest.items()}
