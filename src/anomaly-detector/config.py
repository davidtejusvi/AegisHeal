import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # AWS
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    # Prometheus
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "aimonitor")
    DB_USER: str = os.getenv("DB_USER", "aimonitor")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # Detection thresholds
    ANOMALY_THRESHOLD_CRITICAL: float = 0.9
    ANOMALY_THRESHOLD_HIGH: float = 0.7
    ANOMALY_THRESHOLD_MEDIUM: float = 0.5

    # Model settings
    ISOLATION_FOREST_CONTAMINATION: float = 0.05
    LSTM_SEQUENCE_LENGTH: int = 20
    LSTM_HIDDEN_SIZE: int = 64

    # Metrics collection window (seconds)
    METRICS_WINDOW_SECONDS: int = 300   # 5 minutes
    METRICS_RESOLUTION_SECONDS: int = 60


config = Config()
