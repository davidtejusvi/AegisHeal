"""
auto-scaler Lambda
------------------
Triggered by: CloudWatch Alarm → SNS → Lambda  (or direct invocation)
Purpose:      Scale up an EKS deployment or ASG when CPU / load is high.
"""
import json
import logging
import os
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION        = os.environ.get("AWS_REGION", "us-east-1")
EKS_CLUSTER_NAME  = os.environ.get("EKS_CLUSTER_NAME", "ai-monitor-dev-eks")
MAX_REPLICAS      = int(os.environ.get("MAX_REPLICAS", "10"))
SCALE_FACTOR      = float(os.environ.get("SCALE_FACTOR", "1.5"))   # 50 % increase

eks_client  = boto3.client("eks",            region_name=AWS_REGION)
asg_client  = boto3.client("autoscaling",    region_name=AWS_REGION)
sns_client  = boto3.client("sns",            region_name=AWS_REGION)
SNS_TOPIC   = os.environ.get("SNS_ALERT_TOPIC_ARN", "")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _notify(subject: str, message: str) -> None:
    if not SNS_TOPIC:
        return
    try:
        sns_client.publish(TopicArn=SNS_TOPIC, Subject=subject, Message=message)
    except ClientError as exc:
        logger.warning("SNS publish failed: %s", exc)


def _scale_asg(asg_name: str, current: int) -> dict:
    target = min(int(current * SCALE_FACTOR) + 1, MAX_REPLICAS)
    if target <= current:
        return {"skipped": True, "reason": "already_at_max", "current": current}
    try:
        asg_client.set_desired_capacity(
            AutoScalingGroupName=asg_name,
            DesiredCapacity=target,
            HonorCooldown=True,
        )
        logger.info("ASG %s scaled from %d → %d", asg_name, current, target)
        return {"scaled": True, "asg": asg_name, "from": current, "to": target}
    except ClientError as exc:
        logger.error("ASG scale failed: %s", exc)
        return {"scaled": False, "error": str(exc)}


def _get_asg_for_cluster(cluster_name: str) -> tuple[str, int] | tuple[None, None]:
    """Find the first node group ASG for an EKS cluster."""
    try:
        ng_resp = eks_client.list_nodegroups(clusterName=cluster_name)
        if not ng_resp.get("nodegroups"):
            return None, None
        ng_name = ng_resp["nodegroups"][0]
        ng_detail = eks_client.describe_nodegroup(
            clusterName=cluster_name, nodegroupName=ng_name
        )
        resources = ng_detail["nodegroup"].get("resources", {})
        asgs = resources.get("autoScalingGroups", [])
        if not asgs:
            return None, None
        asg_name = asgs[0]["name"]
        # Get current desired capacity
        asg_resp = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
        groups = asg_resp.get("AutoScalingGroups", [])
        current = groups[0]["DesiredCapacity"] if groups else 1
        return asg_name, current
    except ClientError as exc:
        logger.error("Could not look up ASG: %s", exc)
        return None, None


# ── Handler ────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    """
    Accepts two call shapes:
      1. SNS envelope  (from CloudWatch Alarm)
      2. Direct payload: {"service": "...", "current_replicas": N, "action": "scale_up"}
    """
    logger.info("Event: %s", json.dumps(event))

    # Unwrap SNS envelope if present
    if "Records" in event:
        try:
            message = json.loads(event["Records"][0]["Sns"]["Message"])
        except (KeyError, json.JSONDecodeError):
            message = {}
    else:
        message = event

    service          = message.get("service", "unknown")
    current_replicas = int(message.get("current_replicas", 2))
    action           = message.get("action", "scale_up")

    if action != "scale_up":
        return {"statusCode": 200, "body": {"skipped": True, "reason": "action_not_scale_up"}}

    asg_name, current = _get_asg_for_cluster(EKS_CLUSTER_NAME)

    if asg_name is None:
        # Fallback: use the current_replicas from the event
        result = {"skipped": True, "reason": "asg_not_found", "service": service}
    else:
        result = _scale_asg(asg_name, current or current_replicas)

    _notify(
        subject=f"[AI-Monitor] Auto-scale triggered for {service}",
        message=json.dumps(result, indent=2),
    )

    return {"statusCode": 200, "body": result}
