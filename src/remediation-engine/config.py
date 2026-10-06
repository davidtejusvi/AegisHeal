import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # AWS
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCOUNT_ID: str = os.getenv("AWS_ACCOUNT_ID", "123456789012")

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "aimonitor")
    DB_USER: str = os.getenv("DB_USER", "aimonitor")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # Kubernetes
    K8S_NAMESPACE: str = os.getenv("K8S_NAMESPACE", "monitoring-platform")
    K8S_IN_CLUSTER: bool = os.getenv("K8S_IN_CLUSTER", "true").lower() == "true"

    # Remediation behaviour
    DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"
    ACTION_TIMEOUT_SECONDS: int = int(os.getenv("ACTION_TIMEOUT_SECONDS", "120"))
    MAX_SCALE_REPLICAS: int = int(os.getenv("MAX_SCALE_REPLICAS", "10"))

    # Lambda function names (deployed by Terraform)
    LAMBDA_AUTO_SCALER: str = os.getenv("LAMBDA_AUTO_SCALER", "ai-monitor-auto-scaler")
    LAMBDA_INSTANCE_RESTARTER: str = os.getenv("LAMBDA_INSTANCE_RESTARTER", "ai-monitor-instance-restarter")

    # SSM document names
    SSM_RESTART_SERVICE: str = os.getenv("SSM_RESTART_SERVICE", "AI-Monitor-RestartService")
    SSM_CLEAR_CACHE: str = os.getenv("SSM_CLEAR_CACHE", "AI-Monitor-ClearCache")


config = Config()
