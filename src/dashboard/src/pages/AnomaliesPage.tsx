import { useState, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import { anomalyClient } from '../api/client';
import type { AnalyzeRequest, AnalyzeResponse, Severity } from '../api/types';
import { useAnomalies } from '../hooks/useAnomalies';
import { SeverityBadge } from '../components/SeverityBadge';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { format, parseISO } from 'date-fns';
import { Search } from 'lucide-react';
import clsx from 'clsx';

const SCORE_COLOR = (score: number) =>
  score > 0.7 ? 'text-red-400' : score > 0.5 ? 'text-yellow-400' : 'text-green-400';

export function AnomaliesPage() {
  const anomalies = useAnomalies(200);
  const [filterService, setFilterService] = useState('');
  const [filterSeverity, setFilterSeverity] = useState<Severity | ''>('');
  const [filterAnomalyOnly, setFilterAnomalyOnly] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  // Analyze form
  const [form, setForm] = useState<AnalyzeRequest>({
    service: '',
    cpu_utilization: 50,
    memory_utilization: 50,
    request_count: 100,
    error_rate: 0.01,
    latency_p99: 200,
  });
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null);

  const analyzeMutation = useMutation({
    mutationFn: async (req: AnalyzeRequest) => {
      const { data } = await anomalyClient.post<AnalyzeResponse>('/analyze', req);
      return data;
    },
    onSuccess: (data) => setAnalyzeResult(data),
  });

  const filtered = useMemo(() => {
    if (!anomalies.data) return [];
    return anomalies.data.anomalies.filter((a) => {
      if (filterService && !a.service.toLowerCase().includes(filterService.toLowerCase())) return false;
      if (filterSeverity && a.severity !== filterSeverity) return false;
      if (filterAnomalyOnly && !a.is_anomaly) return false;
      return true;
    });
  }, [anomalies.data, filterService, filterSeverity, filterAnomalyOnly]);

  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Anomaly History</h1>
        <p className="text-sm text-slate-400">Detailed anomaly records with ML scores</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Filter by service…"
            value={filterService}
            onChange={(e) => { setFilterService(e.target.value); setPage(0); }}
            className="rounded-lg border border-slate-700 bg-slate-800 pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-cyan-400"
          />
        </div>
        <select
          value={filterSeverity}
          onChange={(e) => { setFilterSeverity(e.target.value as Severity | ''); setPage(0); }}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400"
        >
          <option value="">All Severities</option>
          {(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as Severity[]).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200">
          <input
            type="checkbox"
            checked={filterAnomalyOnly}
            onChange={(e) => { setFilterAnomalyOnly(e.target.checked); setPage(0); }}
            className="accent-cyan-400"
          />
          Anomalies only
        </label>
        <span className="ml-auto self-center text-xs text-slate-400">{filtered.length} records</span>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-700 bg-slate-800 overflow-x-auto">
        {anomalies.isLoading ? (
          <LoadingSpinner />
        ) : paged.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-500">No anomalies match your filters</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-left">
                {['Timestamp', 'Service', 'Score', 'Severity', 'Anomaly?', 'Isolation', 'LSTM', 'Confidence'].map((h) => (
                  <th key={h} className="px-4 py-3 text-slate-400 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paged.map((a, i) => (
                <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors">
                  <td className="px-4 py-2 text-slate-300 whitespace-nowrap">{format(parseISO(a.timestamp), 'MMM d HH:mm:ss')}</td>
                  <td className="px-4 py-2 text-slate-200">{a.service}</td>
                  <td className={clsx('px-4 py-2 font-mono font-semibold', SCORE_COLOR(a.anomaly_score))}>{a.anomaly_score.toFixed(3)}</td>
                  <td className="px-4 py-2"><SeverityBadge severity={a.severity} /></td>
                  <td className="px-4 py-2">{a.is_anomaly ? '✅' : '—'}</td>
                  <td className="px-4 py-2 text-slate-300">{a.isolation_score.toFixed(3)}</td>
                  <td className="px-4 py-2 text-slate-300">{a.lstm_score.toFixed(3)}</td>
                  <td className="px-4 py-2 text-slate-300">{(a.confidence * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 text-slate-300 hover:text-white disabled:opacity-40"
          >Prev</button>
          <span className="text-sm text-slate-400">Page {page + 1} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="rounded px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 text-slate-300 hover:text-white disabled:opacity-40"
          >Next</button>
        </div>
      )}

      {/* Analyze Panel */}
      <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-200">Analyze Service Metrics</h2>
        <form
          onSubmit={(e) => { e.preventDefault(); analyzeMutation.mutate(form); }}
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <div className="col-span-full">
            <label className="block text-xs text-slate-400 mb-1">Service Name</label>
            <input
              type="text"
              required
              value={form.service}
              onChange={(e) => setForm((f) => ({ ...f, service: e.target.value }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400"
              placeholder="e.g. payment-service"
            />
          </div>
          {([
            { key: 'cpu_utilization', label: 'CPU %', min: 0, max: 100, step: 1 },
            { key: 'memory_utilization', label: 'Memory %', min: 0, max: 100, step: 1 },
            { key: 'request_count', label: 'Request Count', min: 0, max: 10000, step: 10 },
            { key: 'error_rate', label: 'Error Rate', min: 0, max: 1, step: 0.001 },
            { key: 'latency_p99', label: 'Latency p99 (ms)', min: 0, max: 5000, step: 10 },
          ] as const).map(({ key, label, min, max, step }) => (
            <div key={key}>
              <label className="block text-xs text-slate-400 mb-1">{label}: {form[key as keyof typeof form]}</label>
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={form[key as keyof typeof form] as number}
                onChange={(e) => setForm((f) => ({ ...f, [key]: parseFloat(e.target.value) }))}
                className="w-full accent-cyan-400"
              />
            </div>
          ))}
          <div className="col-span-full">
            <button
              type="submit"
              disabled={analyzeMutation.isPending}
              className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-cyan-300 disabled:opacity-50 transition-colors"
            >
              {analyzeMutation.isPending ? 'Analyzing…' : 'Analyze'}
            </button>
          </div>
        </form>
        {analyzeResult && (
          <div className="mt-4 rounded-lg bg-slate-900 p-4 text-xs">
            <div className="flex flex-wrap gap-4">
              <span><span className="text-slate-400">Score: </span><span className={clsx('font-mono font-bold', SCORE_COLOR(analyzeResult.anomaly_score))}>{analyzeResult.anomaly_score.toFixed(4)}</span></span>
              <span><span className="text-slate-400">Severity: </span><SeverityBadge severity={analyzeResult.severity} /></span>
              <span><span className="text-slate-400">Anomaly: </span><span className="text-white">{analyzeResult.is_anomaly ? 'Yes' : 'No'}</span></span>
              <span><span className="text-slate-400">Confidence: </span><span className="text-white">{(analyzeResult.confidence * 100).toFixed(1)}%</span></span>
            </div>
            <p className="mt-3 text-slate-300"><span className="text-slate-400">Recommendation: </span>{analyzeResult.recommendation}</p>
          </div>
        )}
      </div>
    </div>
  );
}
