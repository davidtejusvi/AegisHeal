import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { anomalyClient } from '../api/client';
import type { TrainRequest, TrainResponse } from '../api/types';
import { useAnomalyHealth, useRemediationHealth } from '../hooks/useHealth';
import { StatusDot } from '../components/StatusDot';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { RefreshCw } from 'lucide-react';

const EXAMPLE_HISTORY = JSON.stringify(
  Array.from({ length: 25 }, (_, i) => ({
    timestamp: new Date(Date.now() - (25 - i) * 60000).toISOString(),
    service: 'example-service',
    cpu_utilization: 40 + Math.random() * 20,
    memory_utilization: 50 + Math.random() * 20,
    request_count: 100 + Math.floor(Math.random() * 50),
    error_rate: Math.random() * 0.05,
    latency_p99: 150 + Math.random() * 100,
  })),
  null,
  2
);

export function ServicesPage() {
  const anomalyHealth = useAnomalyHealth();
  const remediationHealth = useRemediationHealth();

  const [trainForm, setTrainForm] = useState<TrainRequest>({
    service: 'example-service',
    history: [],
  });
  const [historyJson, setHistoryJson] = useState(EXAMPLE_HISTORY);
  const [jsonError, setJsonError] = useState('');
  const [trainResult, setTrainResult] = useState<TrainResponse | null>(null);

  const trainMutation = useMutation({
    mutationFn: async (req: TrainRequest) => {
      const { data } = await anomalyClient.post<TrainResponse>('/train', req);
      return data;
    },
    onSuccess: (data) => setTrainResult(data),
  });

  function handleTrainSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const parsed = JSON.parse(historyJson) as Record<string, unknown>[];
      setJsonError('');
      trainMutation.mutate({ ...trainForm, history: parsed });
    } catch {
      setJsonError('Invalid JSON — please fix the history payload.');
    }
  }

  const services = [
    {
      name: 'anomaly-detector',
      port: 8000,
      query: anomalyHealth,
      description: 'ML-based anomaly detection (LSTM + Isolation Forest)',
    },
    {
      name: 'remediation-engine',
      port: 8001,
      query: remediationHealth,
      description: 'AI-driven root-cause analysis and automated remediation',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Services</h1>
        <p className="text-sm text-slate-400">Live health status and model management</p>
      </div>

      {/* Service health cards */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {services.map(({ name, port, query, description }) => (
          <div key={name} className="rounded-xl border border-slate-700 bg-slate-800 p-5">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white">{name}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{description}</p>
                <p className="text-xs text-slate-500 mt-1">Port: {port}</p>
              </div>
              <button
                onClick={() => void query.refetch()}
                className="rounded-lg p-2 text-slate-400 hover:text-cyan-400 hover:bg-slate-700 transition-colors"
                aria-label="Refresh health"
              >
                <RefreshCw className={`h-4 w-4 ${query.isFetching ? 'animate-spin' : ''}`} />
              </button>
            </div>

            <div className="mt-4">
              {query.isLoading ? (
                <LoadingSpinner size="sm" />
              ) : query.isError ? (
                <StatusDot healthy={false} />
              ) : (
                <>
                  <StatusDot healthy={query.data?.status === 'healthy'} />
                  <div className="mt-3 space-y-1 text-xs">
                    {query.data?.version && (
                      <p><span className="text-slate-400">Version: </span><span className="text-slate-200">{query.data.version}</span></p>
                    )}
                    {query.data?.model_trained !== undefined && (
                      <p><span className="text-slate-400">Model Trained: </span><span className={query.data.model_trained ? 'text-green-400' : 'text-yellow-400'}>{query.data.model_trained ? 'Yes' : 'No'}</span></p>
                    )}
                    {query.data?.dry_run !== undefined && (
                      <p><span className="text-slate-400">Dry Run: </span><span className={query.data.dry_run ? 'text-yellow-400' : 'text-green-400'}>{query.data.dry_run ? 'Yes' : 'No'}</span></p>
                    )}
                    <p className="text-slate-500">{query.data?.timestamp}</p>
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Train model panel */}
      <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
        <h2 className="mb-1 text-sm font-semibold text-slate-200">Train Anomaly Model</h2>
        <p className="text-xs text-slate-400 mb-4">POST /train — submit historical metric samples to retrain the LSTM model</p>
        <form onSubmit={handleTrainSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Service Name</label>
            <input
              type="text"
              required
              value={trainForm.service}
              onChange={(e) => setTrainForm((f) => ({ ...f, service: e.target.value }))}
              className="w-full max-w-sm rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">History (JSON array of metric objects)</label>
            <textarea
              value={historyJson}
              onChange={(e) => setHistoryJson(e.target.value)}
              rows={10}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400 resize-y"
            />
            {jsonError && <p className="mt-1 text-xs text-red-400">{jsonError}</p>}
          </div>
          <button
            type="submit"
            disabled={trainMutation.isPending}
            className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-cyan-300 disabled:opacity-50 transition-colors"
          >
            {trainMutation.isPending ? 'Training…' : 'Train Model'}
          </button>
        </form>
        {trainResult && (
          <div className="mt-4 rounded-lg bg-slate-900 p-4 text-xs">
            <p><span className="text-slate-400">Status: </span><span className="text-green-400 font-semibold">{trainResult.status}</span></p>
            <p><span className="text-slate-400">Samples: </span><span className="text-white">{trainResult.samples_trained}</span></p>
            <p><span className="text-slate-400">Message: </span><span className="text-slate-200">{trainResult.message}</span></p>
          </div>
        )}
      </div>
    </div>
  );
}
