"""
Anomaly detection using:
  1. Isolation Forest  — good for real-time, one-shot scoring
  2. LSTM Autoencoder  — good for time-series pattern detection
  3. Ensemble          — weighted average of both scores
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from config import config

logger = logging.getLogger(__name__)

FEATURE_KEYS = [
    "cpu_utilization",
    "memory_utilization",
    "request_count",
    "error_rate",
    "latency_p99",
    "disk_io",
    "network_in",
    "network_out",
]


# ── Severity ───────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"
    NORMAL   = "NORMAL"


def score_to_severity(score: float) -> Severity:
    if score >= config.ANOMALY_THRESHOLD_CRITICAL:
        return Severity.CRITICAL
    if score >= config.ANOMALY_THRESHOLD_HIGH:
        return Severity.HIGH
    if score >= config.ANOMALY_THRESHOLD_MEDIUM:
        return Severity.MEDIUM
    if score > 0.0:
        return Severity.LOW
    return Severity.NORMAL


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class AnomalyResult:
    anomaly_score: float          # 0.0 – 1.0
    severity: Severity
    confidence: float             # 0.0 – 1.0
    isolation_score: float
    lstm_score: float
    is_anomaly: bool
    details: dict


# ── LSTM Autoencoder ───────────────────────────────────────────────────────────

class LSTMAutoencoder(nn.Module):
    """Encodes a sequence then reconstructs it; high reconstruction error = anomaly."""

    def __init__(self, input_size: int, hidden_size: int) -> None:
        super().__init__()
        self.encoder = nn.LSTM(input_size, hidden_size, batch_first=True)
        self.decoder = nn.LSTM(hidden_size, input_size, batch_first=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (hidden, _) = self.encoder(x)
        # Repeat hidden state across the sequence length for decoding
        seq_len = x.size(1)
        decoder_input = hidden.permute(1, 0, 2).repeat(1, seq_len, 1)
        out, _ = self.decoder(decoder_input)
        return out


# ── Main detector ──────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Combines Isolation Forest and LSTM Autoencoder into an ensemble detector.
    Call .train(history) once you have historical metric data,
    then .detect(current_metrics) for scoring.
    """

    # Ensemble weights
    _IF_WEIGHT   = 0.5
    _LSTM_WEIGHT = 0.5

    def __init__(self) -> None:
        self._n_features  = len(FEATURE_KEYS)
        self._scaler      = StandardScaler()
        self._iforest     = IsolationForest(
            contamination=config.ISOLATION_FOREST_CONTAMINATION,
            random_state=42,
            n_estimators=100,
        )
        self._lstm        = LSTMAutoencoder(
            input_size=self._n_features,
            hidden_size=config.LSTM_HIDDEN_SIZE,
        )
        self._lstm_threshold: float = 0.5   # updated during training
        self._trained     = False
        self._history: list[np.ndarray] = []   # rolling window for LSTM

    # ── Training ───────────────────────────────────────────────────────────────

    def train(self, metric_history: list[dict[str, float]]) -> None:
        """
        metric_history — list of dicts, each with keys matching FEATURE_KEYS.
        Expects at least config.LSTM_SEQUENCE_LENGTH + 1 samples.
        """
        if len(metric_history) < config.LSTM_SEQUENCE_LENGTH + 1:
            logger.warning("Not enough history to train (%d samples)", len(metric_history))
            return

        X = self._dicts_to_array(metric_history)
        X_scaled = self._scaler.fit_transform(X)

        # Train Isolation Forest
        self._iforest.fit(X_scaled)

        # Train LSTM Autoencoder
        self._train_lstm(X_scaled)

        self._trained = True
        logger.info("AnomalyDetector trained on %d samples", len(metric_history))

    def _train_lstm(self, X_scaled: np.ndarray) -> None:
        seq_len   = config.LSTM_SEQUENCE_LENGTH
        sequences = self._make_sequences(X_scaled, seq_len)
        if len(sequences) == 0:
            return

        dataset = torch.tensor(sequences, dtype=torch.float32)
        optimizer = torch.optim.Adam(self._lstm.parameters(), lr=1e-3)
        criterion = nn.MSELoss()

        self._lstm.train()
        for epoch in range(30):
            optimizer.zero_grad()
            reconstructed = self._lstm(dataset)
            loss = criterion(reconstructed, dataset)
            loss.backward()
            optimizer.step()
            if epoch % 10 == 0:
                logger.debug("LSTM epoch %d — loss: %.6f", epoch, loss.item())

        # Compute reconstruction errors to set threshold (95th percentile)
        self._lstm.eval()
        with torch.no_grad():
            recon = self._lstm(dataset)
            errors = ((recon - dataset) ** 2).mean(dim=(1, 2)).numpy()
        self._lstm_threshold = float(np.percentile(errors, 95))
        logger.debug("LSTM threshold set to %.6f", self._lstm_threshold)

    # ── Detection ──────────────────────────────────────────────────────────────

    def detect(self, current_metrics: dict[str, float]) -> AnomalyResult:
        if not self._trained:
            logger.warning("Model not trained — returning zero scores")
            return self._zero_result()

        x = self._dict_to_row(current_metrics)
        x_scaled = self._scaler.transform(x.reshape(1, -1))

        if_score   = self._isolation_score(x_scaled)
        lstm_score = self._lstm_score(x_scaled)

        # Ensemble
        ensemble = self._IF_WEIGHT * if_score + self._LSTM_WEIGHT * lstm_score
        ensemble = float(np.clip(ensemble, 0.0, 1.0))

        # Confidence: how far the score is from the 0.5 midpoint
        confidence = abs(ensemble - 0.5) * 2.0

        severity   = score_to_severity(ensemble)
        is_anomaly = ensemble >= config.ANOMALY_THRESHOLD_MEDIUM

        # Roll history
        self._history.append(x_scaled[0])
        if len(self._history) > config.LSTM_SEQUENCE_LENGTH * 2:
            self._history.pop(0)

        return AnomalyResult(
            anomaly_score    = ensemble,
            severity         = severity,
            confidence       = round(confidence, 4),
            isolation_score  = round(if_score, 4),
            lstm_score       = round(lstm_score, 4),
            is_anomaly       = is_anomaly,
            details          = {
                "features_used":  FEATURE_KEYS,
                "missing_features": [k for k in FEATURE_KEYS if k not in current_metrics],
            },
        )

    def _isolation_score(self, x_scaled: np.ndarray) -> float:
        """Map Isolation Forest's raw score (-1..1) to 0..1 (higher = more anomalous)."""
        raw = self._iforest.score_samples(x_scaled)[0]
        # score_samples returns lower values for anomalies
        return float(np.clip((raw * -1 + 0.5), 0.0, 1.0))

    def _lstm_score(self, x_scaled: np.ndarray) -> float:
        if len(self._history) < config.LSTM_SEQUENCE_LENGTH:
            return 0.0

        seq = np.array(self._history[-config.LSTM_SEQUENCE_LENGTH:])
        seq_t = torch.tensor(seq, dtype=torch.float32).unsqueeze(0)

        self._lstm.eval()
        with torch.no_grad():
            recon = self._lstm(seq_t)
            error = float(((recon - seq_t) ** 2).mean().item())

        if self._lstm_threshold == 0:
            return 0.0
        return float(np.clip(error / (self._lstm_threshold * 2), 0.0, 1.0))

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _dicts_to_array(self, data: list[dict[str, float]]) -> np.ndarray:
        return np.array([self._dict_to_row(d) for d in data])

    def _dict_to_row(self, d: dict[str, float]) -> np.ndarray:
        return np.array([d.get(k, 0.0) for k in FEATURE_KEYS], dtype=np.float32)

    @staticmethod
    def _make_sequences(X: np.ndarray, seq_len: int) -> np.ndarray:
        seqs = [X[i : i + seq_len] for i in range(len(X) - seq_len + 1)]
        return np.array(seqs) if seqs else np.empty((0, seq_len, X.shape[1]))

    @staticmethod
    def _zero_result() -> AnomalyResult:
        return AnomalyResult(
            anomaly_score   = 0.0,
            severity        = Severity.NORMAL,
            confidence      = 0.0,
            isolation_score = 0.0,
            lstm_score      = 0.0,
            is_anomaly      = False,
            details         = {"reason": "model_not_trained"},
        )
