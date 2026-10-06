"""
Remediation actions — executes fixes via Lambda, SSM, and Kubernetes.
Every action supports dry_run mode and returns a structured result.
"""
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import boto3
from botocore.exceptions import ClientError
from kubernetes import client as k8s_client, config as k8s_config

from config import config

logger = logging.getLogger(__name__)


class ActionStatus(str, Enum):
    SUCCESS  = "success"
    FAILED   = "failed"
    DRY_RUN  = "dry_run"
    SKIPPED  = "skipped"


@dataclass
class ActionResult:
    action:     str
    status:     ActionStatus
    message:    str
    duration_s: float
    details:    dict[str, Any]


# ── Base helper ────────────────────────────────────────────────────────────────

def _timed(fn):
    """Wrap a callable, return (result, elapsed_seconds)."""
    start = time.monotonic()
    result = fn()
    return result, round(time.monotonic() - start, 3)


# ── Lambda actions ─────────────────────────────────────────────────────────────

class LambdaActions:

    def __init__(self) -> None:
        self._client = boto3.client("lambda", region_name=config.AWS_REGION)

    def invoke(self, function_name: str, payload: dict) -> ActionResult:
        action = f"lambda:{function_name}"
        if config.DRY_RUN:
            return ActionResult(action, ActionStatus.DRY_RUN, "Dry run — skipped", 0.0, {})

        def _call():
            return self._client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode(),
            )

        try:
            response, elapsed = _timed(_call)
            status_code = response.get("StatusCode", 0)
            body = json.loads(response["Payload"].read())
            if status_code == 200:
                return ActionResult(action, ActionStatus.SUCCESS, "Lambda invoked", elapsed, body)
            return ActionResult(action, ActionStatus.FAILED, f"Status {status_code}", elapsed, body)
        except ClientError as exc:
            return ActionResult(action, ActionStatus.FAILED, str(exc), 0.0, {})

    def trigger_auto_scaler(self, service: str, current_count: int) -> ActionResult:
        return self.invoke(
            config.LAMBDA_AUTO_SCALER,
            {"service": service, "current_replicas": current_count, "action": "scale_up"},
        )

    def trigger_instance_restarter(self, service: str) -> ActionResult:
        return self.invoke(
            config.LAMBDA_INSTANCE_RESTARTER,
            {"service": service, "action": "restart"},
        )


# ── SSM actions ────────────────────────────────────────────────────────────────

class SSMActions:

    def __init__(self) -> None:
        self._client = boto3.client("ssm", region_name=config.AWS_REGION)

    def run_document(
        self,
        document_name: str,
        targets: list[dict],
        parameters: dict[str, list[str]] | None = None,
    ) -> ActionResult:
        action = f"ssm:{document_name}"
        if config.DRY_RUN:
            return ActionResult(action, ActionStatus.DRY_RUN, "Dry run — skipped", 0.0, {})

        def _call():
            return self._client.send_command(
                DocumentName=document_name,
                Targets=targets,
                Parameters=parameters or {},
                TimeoutSeconds=config.ACTION_TIMEOUT_SECONDS,
            )

        try:
            response, elapsed = _timed(_call)
            command_id = response["Command"]["CommandId"]
            return ActionResult(
                action, ActionStatus.SUCCESS,
                f"SSM command {command_id} sent", elapsed,
                {"command_id": command_id},
            )
        except ClientError as exc:
            return ActionResult(action, ActionStatus.FAILED, str(exc), 0.0, {})

    def restart_service(self, instance_ids: list[str], service_name: str) -> ActionResult:
        return self.run_document(
            config.SSM_RESTART_SERVICE,
            targets=[{"Key": "InstanceIds", "Values": instance_ids}],
            parameters={"ServiceName": [service_name]},
        )

    def clear_cache(self, instance_ids: list[str]) -> ActionResult:
        return self.run_document(
            config.SSM_CLEAR_CACHE,
            targets=[{"Key": "InstanceIds", "Values": instance_ids}],
        )


# ── Kubernetes actions ─────────────────────────────────────────────────────────

class KubernetesActions:

    def __init__(self) -> None:
        try:
            if config.K8S_IN_CLUSTER:
                k8s_config.load_incluster_config()
            else:
                k8s_config.load_kube_config()
            self._apps  = k8s_client.AppsV1Api()
            self._core  = k8s_client.CoreV1Api()
            self._ready = True
        except Exception as exc:
            logger.warning("Kubernetes not available: %s", exc)
            self._ready = False

    def _unavailable(self, action: str) -> ActionResult:
        return ActionResult(action, ActionStatus.SKIPPED, "Kubernetes not available", 0.0, {})

    def scale_deployment(self, deployment: str, replicas: int) -> ActionResult:
        action = f"k8s:scale:{deployment}"
        if not self._ready:
            return self._unavailable(action)
        if config.DRY_RUN:
            return ActionResult(action, ActionStatus.DRY_RUN, "Dry run — skipped", 0.0, {})

        replicas = min(replicas, config.MAX_SCALE_REPLICAS)

        def _call():
            return self._apps.patch_namespaced_deployment_scale(
                name=deployment,
                namespace=config.K8S_NAMESPACE,
                body={"spec": {"replicas": replicas}},
            )

        try:
            _, elapsed = _timed(_call)
            return ActionResult(
                action, ActionStatus.SUCCESS,
                f"Scaled {deployment} to {replicas} replicas", elapsed,
                {"deployment": deployment, "replicas": replicas},
            )
        except k8s_client.ApiException as exc:
            return ActionResult(action, ActionStatus.FAILED, str(exc), 0.0, {})

    def restart_pods(self, deployment: str) -> ActionResult:
        """Triggers a rolling restart by patching the deployment annotation."""
        action = f"k8s:restart:{deployment}"
        if not self._ready:
            return self._unavailable(action)
        if config.DRY_RUN:
            return ActionResult(action, ActionStatus.DRY_RUN, "Dry run — skipped", 0.0, {})

        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": str(time.time())}
                    }
                }
            }
        }

        def _call():
            return self._apps.patch_namespaced_deployment(
                name=deployment,
                namespace=config.K8S_NAMESPACE,
                body=patch,
            )

        try:
            _, elapsed = _timed(_call)
            return ActionResult(
                action, ActionStatus.SUCCESS,
                f"Rolling restart triggered for {deployment}", elapsed,
                {"deployment": deployment},
            )
        except k8s_client.ApiException as exc:
            return ActionResult(action, ActionStatus.FAILED, str(exc), 0.0, {})

    def rollback_deployment(self, deployment: str) -> ActionResult:
        """Rolls back to the previous ReplicaSet revision."""
        action = f"k8s:rollback:{deployment}"
        if not self._ready:
            return self._unavailable(action)
        if config.DRY_RUN:
            return ActionResult(action, ActionStatus.DRY_RUN, "Dry run — skipped", 0.0, {})

        def _call():
            return self._apps.patch_namespaced_deployment(
                name=deployment,
                namespace=config.K8S_NAMESPACE,
                body={"spec": {"rollbackTo": {"revision": 0}}},
            )

        try:
            _, elapsed = _timed(_call)
            return ActionResult(
                action, ActionStatus.SUCCESS,
                f"Rollback triggered for {deployment}", elapsed,
                {"deployment": deployment},
            )
        except k8s_client.ApiException as exc:
            return ActionResult(action, ActionStatus.FAILED, str(exc), 0.0, {})


# ── Unified handler ────────────────────────────────────────────────────────────

class RemediationHandler:
    """
    Dispatches remediation actions based on the recommended_actions
    list from the RCA result.
    """

    ACTION_MAP = {
        "trigger_auto_scaler":    "_do_trigger_auto_scaler",
        "trigger_instance_restarter": "_do_trigger_instance_restarter",
        "scale_out_kubernetes":   "_do_scale_out_kubernetes",
        "restart_pods":           "_do_restart_pods",
        "rollback_deployment":    "_do_rollback_deployment",
        "ssm_restart_service":    "_do_ssm_restart_service",
        "ssm_clear_cache":        "_do_ssm_clear_cache",
    }

    def __init__(self) -> None:
        self._lambda = LambdaActions()
        self._ssm    = SSMActions()
        self._k8s    = KubernetesActions()

    def execute(
        self,
        service: str,
        recommended_actions: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[ActionResult]:
        ctx = context or {}
        results: list[ActionResult] = []

        for action_name in recommended_actions:
            method_name = self.ACTION_MAP.get(action_name)
            if not method_name:
                logger.warning("Unknown action: %s", action_name)
                continue
            method = getattr(self, method_name)
            result = method(service, ctx)
            results.append(result)
            logger.info("Action %s → %s: %s", action_name, result.status.value, result.message)

            # Stop after first successful action (avoid over-remediating)
            if result.status == ActionStatus.SUCCESS:
                break

        return results

    # ── Private action implementations ────────────────────────────────────────

    def _do_trigger_auto_scaler(self, service: str, ctx: dict) -> ActionResult:
        current = ctx.get("current_replicas", 2)
        return self._lambda.trigger_auto_scaler(service, current)

    def _do_trigger_instance_restarter(self, service: str, ctx: dict) -> ActionResult:
        return self._lambda.trigger_instance_restarter(service)

    def _do_scale_out_kubernetes(self, service: str, ctx: dict) -> ActionResult:
        current  = ctx.get("current_replicas", 2)
        target   = min(current * 2, config.MAX_SCALE_REPLICAS)
        return self._k8s.scale_deployment(service, target)

    def _do_restart_pods(self, service: str, ctx: dict) -> ActionResult:
        return self._k8s.restart_pods(service)

    def _do_rollback_deployment(self, service: str, ctx: dict) -> ActionResult:
        return self._k8s.rollback_deployment(service)

    def _do_ssm_restart_service(self, service: str, ctx: dict) -> ActionResult:
        instance_ids = ctx.get("instance_ids", [])
        if not instance_ids:
            return ActionResult(
                "ssm:restart_service", ActionStatus.SKIPPED,
                "No instance IDs provided", 0.0, {},
            )
        return self._ssm.restart_service(instance_ids, service)

    def _do_ssm_clear_cache(self, service: str, ctx: dict) -> ActionResult:
        instance_ids = ctx.get("instance_ids", [])
        if not instance_ids:
            return ActionResult(
                "ssm:clear_cache", ActionStatus.SKIPPED,
                "No instance IDs provided", 0.0, {},
            )
        return self._ssm.clear_cache(instance_ids)
