"""
instance-restarter Lambda
--------------------------
Triggered by: CloudWatch Alarm → SNS → Lambda  (or direct invocation)
Purpose:      Find unhealthy EC2 instances in a target ASG / tag group,
              stop-and-start them (not terminate), and verify recovery.
"""
import json
import logging
import os
import time
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION   = os.environ.get("AWS_REGION", "us-east-1")
HEALTH_TAG   = os.environ.get("HEALTH_TAG_KEY", "ai-monitor-managed")
SNS_TOPIC    = os.environ.get("SNS_ALERT_TOPIC_ARN", "")
WAIT_SECONDS = int(os.environ.get("WAIT_AFTER_START_SECONDS", "30"))

ec2_client = boto3.client("ec2",  region_name=AWS_REGION)
sns_client = boto3.client("sns",  region_name=AWS_REGION)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _notify(subject: str, message: str) -> None:
    if not SNS_TOPIC:
        return
    try:
        sns_client.publish(TopicArn=SNS_TOPIC, Subject=subject, Message=message)
    except ClientError as exc:
        logger.warning("SNS publish failed: %s", exc)


def _find_unhealthy_instances(service: str) -> list[str]:
    """Return instance IDs that are running but fail status checks."""
    try:
        resp = ec2_client.describe_instance_status(
            Filters=[
                {"Name": "instance-state-name", "Values": ["running"]},
                {"Name": "instance-status.status", "Values": ["impaired"]},
            ],
            IncludeAllInstances=False,
        )
        ids = [i["InstanceId"] for i in resp.get("InstanceStatuses", [])]
        logger.info("Found %d unhealthy instances for service '%s'", len(ids), service)
        return ids
    except ClientError as exc:
        logger.error("describe_instance_status failed: %s", exc)
        return []


def _restart_instance(instance_id: str) -> dict:
    """Stop then start a single instance. Returns result dict."""
    try:
        logger.info("Stopping %s", instance_id)
        ec2_client.stop_instances(InstanceIds=[instance_id])

        # Wait for stopped state (poll up to 90 s)
        waiter = ec2_client.get_waiter("instance_stopped")
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={"Delay": 5, "MaxAttempts": 18},
        )

        logger.info("Starting %s", instance_id)
        ec2_client.start_instances(InstanceIds=[instance_id])

        # Brief pause then verify
        time.sleep(WAIT_SECONDS)
        status_resp = ec2_client.describe_instance_status(InstanceIds=[instance_id])
        statuses = status_resp.get("InstanceStatuses", [])
        recovered = (
            statuses
            and statuses[0]["InstanceStatus"]["Status"] == "ok"
            and statuses[0]["SystemStatus"]["Status"] == "ok"
        )
        return {
            "instance_id": instance_id,
            "restarted":   True,
            "recovered":   recovered,
        }
    except ClientError as exc:
        logger.error("Restart failed for %s: %s", instance_id, exc)
        return {"instance_id": instance_id, "restarted": False, "error": str(exc)}


# ── Handler ────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    logger.info("Event: %s", json.dumps(event))

    # Unwrap SNS envelope if present
    if "Records" in event:
        try:
            message = json.loads(event["Records"][0]["Sns"]["Message"])
        except (KeyError, json.JSONDecodeError):
            message = {}
    else:
        message = event

    service = message.get("service", "unknown")
    action  = message.get("action", "restart")

    if action != "restart":
        return {"statusCode": 200, "body": {"skipped": True, "reason": "action_not_restart"}}

    instance_ids = _find_unhealthy_instances(service)

    if not instance_ids:
        return {
            "statusCode": 200,
            "body": {"message": "No unhealthy instances found", "service": service},
        }

    results = [_restart_instance(iid) for iid in instance_ids[:3]]   # cap at 3 per invocation

    summary = {
        "service":           service,
        "instances_targeted": len(results),
        "recovered":         sum(1 for r in results if r.get("recovered")),
        "details":           results,
    }

    _notify(
        subject=f"[AI-Monitor] Instance restart completed for {service}",
        message=json.dumps(summary, indent=2),
    )

    return {"statusCode": 200, "body": summary}
