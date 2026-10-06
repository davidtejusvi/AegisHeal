// Anomaly Detector API types
export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  service: string;
  version: string;
  model_trained?: boolean;
  dry_run?: boolean;
  timestamp: string;
}

export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface AnomalyRecord {
  timestamp: string;
  service: string;
  anomaly_score: number;
  severity: Severity;
  is_anomaly: boolean;
  isolation_score: number;
  lstm_score: number;
  confidence: number;
  cpu_utilization?: number;
  memory_utilization?: number;
  request_count?: number;
  error_rate?: number;
  latency_p99?: number;
}

export interface AnomaliesResponse {
  anomalies: AnomalyRecord[];
  total: number;
  limit: number;
}

export interface AnalyzeRequest {
  service: string;
  cpu_utilization: number;
  memory_utilization: number;
  request_count: number;
  error_rate: number;
  latency_p99: number;
}

export interface AnalyzeResponse {
  service: string;
  anomaly_score: number;
  severity: Severity;
  is_anomaly: boolean;
  confidence: number;
  isolation_score: number;
  lstm_score: number;
  recommendation: string;
  timestamp: string;
}

export interface TrainRequest {
  service: string;
  history: Record<string, unknown>[];
}

export interface TrainResponse {
  status: string;
  service: string;
  samples_trained: number;
  message: string;
}

// Remediation Engine API types
export interface IncidentRecord {
  incident_id: string;
  service: string;
  severity: Severity;
  root_cause: string;
  mttr_seconds: number;
  auto_resolved: boolean;
  resolved_at: string;
  created_at?: string;
  remediation_action?: string;
  failure_type?: string;
}

export interface IncidentsResponse {
  incidents: IncidentRecord[];
  total: number;
  limit: number;
}

export interface RootCauseBreakdown {
  [key: string]: number;
}

export interface StatsResponse {
  total_incidents: number;
  auto_resolved: number;
  auto_resolution_rate_pct: number;
  avg_mttr_seconds: number;
  root_cause_breakdown: RootCauseBreakdown;
  severity_breakdown?: Record<string, number>;
}

export interface SimulateRequest {
  service: string;
  failure_type: 'cpu_spike' | 'memory_pressure' | 'high_error_rate' | 'latency_spike';
}

export interface SimulateResponse {
  incident_id: string;
  service: string;
  failure_type: string;
  severity: Severity;
  root_cause: string;
  remediation_action: string;
  estimated_mttr_seconds: number;
  auto_resolve: boolean;
  timestamp: string;
}

export interface RemediateRequest {
  incident_id: string;
  action: string;
}

export interface RemediateResponse {
  status: string;
  incident_id: string;
  action_taken: string;
  result: string;
  timestamp: string;
}
