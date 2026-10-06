import axios from 'axios';

const ANOMALY_URL = import.meta.env.VITE_ANOMALY_DETECTOR_URL ?? 'http://localhost:8000';
const REMEDIATION_URL = import.meta.env.VITE_REMEDIATION_ENGINE_URL ?? 'http://localhost:8001';

export const anomalyClient = axios.create({
  baseURL: ANOMALY_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

export const remediationClient = axios.create({
  baseURL: REMEDIATION_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

// Response interceptors for error normalisation
[anomalyClient, remediationClient].forEach((client) => {
  client.interceptors.response.use(
    (res) => res,
    (err) => {
      console.error('[API error]', err?.response?.data ?? err.message);
      return Promise.reject(err);
    }
  );
});
