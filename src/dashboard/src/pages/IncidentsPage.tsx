import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { remediationClient } from '../api/client';
import type { SimulateRequest, SimulateResponse, Severity } from '../api/types';
import { useIncidents } from '../hooks/useIncidents';
import { useStats } from '../hooks/useStats';
import { KpiCard } from '../components/KpiCard';
import { SeverityBadge } from '../components/SeverityBadge';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { format, parseISO } from 'date-fns';
import { Activity, AlertTriangle, CheckCircle, Clock } from 'lucide-react';

const FAILURE_TYPES: SimulateRequest['failure_type'][] = [
  'cpu_spike', 'memory_pressure', 'high_error_rate', 'latency_spike',
];

export function IncidentsPage() {
  const incidents = useIncidents(100);
  const stats = useStats();

  const [simForm, setSimForm] = useState<SimulateRequest>({ service: '', failure_type: 'cpu_spike' });
  const [simResult, setSimResult] = useState<SimulateResponse | null>(null);

  const simulateMutation = useMutation({
    mutationFn: async (req: SimulateRequest) => {
      const { data } = await remediationClient.post<SimulateResponse>('/simulate', req);
      return data;
    },
    onSuccess: (data) => setSimResult(data),
  });

  const mttrData = (incidents.data?.incidents ?? [])
    .filter((i) => i.mttr_seconds > 0)
    .slice(-30)
    .map((i, idx) => ({ idx: idx + 1, mttr: i.mttr_seconds, service: i.service }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Incident History</h1>
        <p className="text-sm text-slate-400">All recorded incidents and remediation outcomes</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {stats.isLoading ? <div className="col-span-4"><LoadingSpinner /></div> : (
          <>
            <KpiCard title="Total Incidents" value={stats.data?.total_incidents ?? '—'} icon={<AlertTriangle className="h-5 w-5" />} />
            <KpiCard title="Auto Resolved" value={stats.data?.auto_resolved ?? '—'} icon={<CheckCircle className="h-5 w-5" />} />
            <KpiCard title="Resolution Rate" value={stats.data ? `${stats.data.auto_resolution_rate_pct.toFixed(1)}%` : '—'} icon={<Activity className="h-5 w-5" />} />
            <KpiCard title="Avg MTTR" value={stats.data ? `${stats.data.avg_mttr_seconds.toFixed(0)}s` : '—'} icon={<Clock className="h-5 w-5" />} />
          </>
        )}
      </div>

      {/* MTTR chart */}
      <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-200">MTTR Trend (last 30 incidents)</h2>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={mttrData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="idx" tick={{fill: '#94a3b8', fontSize: 11}} />
            <YAxis tick={{fill: '#94a3b8', fontSize: 11}} unit="s" />
            <Tooltip contentStyle={{background: '#1e293b', border: '1px solid #334155', borderRadius: 8}} />
            <Line type="monotone" dataKey="mttr" stroke="#22d3ee" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Incidents table */}
      <div className="rounded-xl border border-slate-700 bg-slate-800 overflow-x-auto">
        <div className="p-4 border-b border-slate-700">
          <h2 className="text-sm font-semibold text-slate-200">All Incidents</h2>
        </div>
        {incidents.isLoading ? (
          <LoadingSpinner />
        ) : !incidents.data?.incidents.length ? (
          <p className="p-8 text-center text-sm text-slate-500">No incidents found — system is healthy 🎉</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-left">
                {['Incident ID', 'Service', 'Severity', 'Root Cause', 'MTTR', 'Auto?', 'Resolved At'].map((h) => (
                  <th key={h} className="px-4 py-3 text-slate-400 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {incidents.data.incidents.map((inc) => (
                <tr key={inc.incident_id} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors">
                  <td className="px-4 py-2 font-mono text-slate-300">{inc.incident_id.slice(0, 12)}…</td>
                  <td className="px-4 py-2 text-slate-200">{inc.service}</td>
                  <td className="px-4 py-2"><SeverityBadge severity={inc.severity as Severity} /></td>
                  <td className="px-4 py-2 text-slate-300 max-w-[200px] truncate">{inc.root_cause}</td>
                  <td className="px-4 py-2 text-slate-300">{inc.mttr_seconds}s</td>
                  <td className="px-4 py-2">{inc.auto_resolved ? '✅' : '❌'}</td>
                  <td className="px-4 py-2 text-slate-300 whitespace-nowrap">
                    {inc.resolved_at ? format(parseISO(inc.resolved_at), 'MMM d HH:mm') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Simulate panel */}
      <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-200">Simulate Failure</h2>
        <form
          onSubmit={(e) => { e.preventDefault(); simulateMutation.mutate(simForm); }}
          className="flex flex-wrap gap-4 items-end"
        >
          <div>
            <label className="block text-xs text-slate-400 mb-1">Service Name</label>
            <input
              type="text"
              required
              value={simForm.service}
              onChange={(e) => setSimForm((f) => ({ ...f, service: e.target.value }))}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400"
              placeholder="e.g. api-gateway"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Failure Type</label>
            <select
              value={simForm.failure_type}
              onChange={(e) => setSimForm((f) => ({ ...f, failure_type: e.target.value as SimulateRequest['failure_type'] }))}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400"
            >
              {FAILURE_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
            </select>
          </div>
          <button
            type="submit"
            disabled={simulateMutation.isPending}
            className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-cyan-300 disabled:opacity-50 transition-colors"
          >
            {simulateMutation.isPending ? 'Simulating…' : 'Simulate'}
          </button>
        </form>
        {simResult && (
          <pre className="mt-4 rounded-lg bg-slate-900 p-4 text-xs text-green-300 overflow-x-auto">
            {JSON.stringify(simResult, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
