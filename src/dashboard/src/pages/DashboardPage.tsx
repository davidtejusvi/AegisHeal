import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  RadialBarChart,
  RadialBar,
} from 'recharts';
import { Activity, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { useAnomalies } from '../hooks/useAnomalies';
import { useIncidents } from '../hooks/useIncidents';
import { useStats } from '../hooks/useStats';
import { KpiCard } from '../components/KpiCard';
import { SeverityBadge } from '../components/SeverityBadge';
import { LoadingSpinner } from '../components/LoadingSpinner';
import type { Severity } from '../api/types';

const DONUT_COLORS = ['#22d3ee', '#818cf8', '#fb923c', '#f472b6', '#a3e635', '#facc15'];

function AnomalyScoreChart({ data }: { data: { timestamp: string; score: number; service: string }[] }) {
  const chartData = data.slice(-30).map((d) => ({
    time: format(parseISO(d.timestamp), 'HH:mm'),
    score: d.score,
    service: d.service,
  }));

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
      <h2 className="mb-4 text-sm font-semibold text-slate-200">Anomaly Score Trend (last 30)</h2>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="time" tick={{fill: '#94a3b8', fontSize: 11}} />
          <YAxis domain={[0, 1]} tick={{fill: '#94a3b8', fontSize: 11}} />
          <Tooltip
            contentStyle={{background: '#1e293b', border: '1px solid #334155', borderRadius: 8}}
            labelStyle={{color: '#94a3b8'}}
          />
          {/* severity reference areas rendered via custom logic */}
          <Line
            type="monotone"
            dataKey="score"
            stroke="#22d3ee"
            strokeWidth={2}
            dot={(props) => {
              const { cx, cy, payload } = props;
              const score = payload.score as number;
              const color = score > 0.7 ? '#ef4444' : score > 0.5 ? '#facc15' : '#4ade80';
              return <circle key={`dot-${cx}-${cy}`} cx={cx} cy={cy} r={3} fill={color} stroke="none" />;
            }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-2 flex gap-4 text-xs text-slate-400">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-400" /> Normal (&lt;0.5)</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-yellow-400" /> Warning (0.5-0.7)</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-400" /> Critical (&gt;0.7)</span>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const anomalies = useAnomalies(30);
  const incidents = useIncidents(10);
  const stats = useStats();

  const anomalyChartData = useMemo(() => {
    if (!anomalies.data) return [];
    return anomalies.data.anomalies.map((a) => ({
      timestamp: a.timestamp,
      score: a.anomaly_score,
      service: a.service,
    }));
  }, [anomalies.data]);

  const donutData = useMemo(() => {
    if (!stats.data?.root_cause_breakdown) return [];
    return Object.entries(stats.data.root_cause_breakdown).map(([name, value]) => ({ name, value }));
  }, [stats.data]);

  const gaugeData = useMemo(() => {
    const rate = stats.data?.auto_resolution_rate_pct ?? 0;
    return [{ name: 'Auto-Resolved', value: rate, fill: '#22d3ee' }];
  }, [stats.data]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Platform Overview</h1>
        <p className="text-sm text-slate-400">Real-time AI-powered infrastructure monitoring</p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {stats.isLoading ? (
          <div className="col-span-4"><LoadingSpinner /></div>
        ) : (
          <>
            <KpiCard
              title="Total Incidents"
              value={stats.data?.total_incidents ?? '—'}
              subtitle="All time"
              icon={<AlertTriangle className="h-5 w-5" />}
            />
            <KpiCard
              title="Auto Resolved"
              value={stats.data?.auto_resolved ?? '—'}
              subtitle="By remediation engine"
              icon={<CheckCircle className="h-5 w-5" />}
            />
            <KpiCard
              title="Resolution Rate"
              value={stats.data ? `${stats.data.auto_resolution_rate_pct.toFixed(1)}%` : '—'}
              subtitle="Auto-resolved / total"
              icon={<Activity className="h-5 w-5" />}
            />
            <KpiCard
              title="Avg MTTR"
              value={stats.data ? `${stats.data.avg_mttr_seconds.toFixed(0)}s` : '—'}
              subtitle="Mean time to remediate"
              icon={<Clock className="h-5 w-5" />}
            />
          </>
        )}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          {anomalies.isLoading ? <LoadingSpinner /> : <AnomalyScoreChart data={anomalyChartData} />}
        </div>

        <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-200">Root Cause Breakdown</h2>
          {stats.isLoading ? (
            <LoadingSpinner />
          ) : donutData.length === 0 ? (
            <p className="text-center text-sm text-slate-500 py-10">No data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={donutData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  dataKey="value"
                  paddingAngle={3}
                >
                  {donutData.map((_, i) => (
                    <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{background: '#1e293b', border: '1px solid #334155', borderRadius: 8}}
                />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  formatter={(value) => <span style={{color: '#94a3b8', fontSize: 11}}>{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Auto-resolution gauge + active incidents */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-4">
        <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-200">Auto-Resolution Rate</h2>
          <ResponsiveContainer width="100%" height={160}>
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="60%"
              outerRadius="90%"
              data={gaugeData}
              startAngle={180}
              endAngle={0}
            >
              <RadialBar
                dataKey="value"
                cornerRadius={6}
                background={{fill: '#334155'}}
              />
              <text x="50%" y="55%" textAnchor="middle" dominantBaseline="middle" fill="#22d3ee" fontSize={22} fontWeight="bold">
                {gaugeData[0]?.value.toFixed(0) ?? 0}%
              </text>
            </RadialBarChart>
          </ResponsiveContainer>
        </div>

        <div className="xl:col-span-3 rounded-xl border border-slate-700 bg-slate-800 p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-200">Recent Incidents</h2>
          {incidents.isLoading ? (
            <LoadingSpinner />
          ) : !incidents.data?.incidents.length ? (
            <p className="text-center text-sm text-slate-500 py-8">No incidents recorded yet — system is healthy 🎉</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700 text-left">
                    {['ID', 'Service', 'Severity', 'Root Cause', 'MTTR', 'Auto?'].map((h) => (
                      <th key={h} className="pb-2 pr-4 text-slate-400 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {incidents.data.incidents.slice(0, 10).map((inc) => (
                    <tr key={inc.incident_id} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors">
                      <td className="py-2 pr-4 font-mono text-slate-300">{inc.incident_id.slice(0, 8)}…</td>
                      <td className="py-2 pr-4 text-slate-200">{inc.service}</td>
                      <td className="py-2 pr-4"><SeverityBadge severity={inc.severity as Severity} /></td>
                      <td className="py-2 pr-4 text-slate-300 max-w-[160px] truncate">{inc.root_cause}</td>
                      <td className="py-2 pr-4 text-slate-300">{inc.mttr_seconds}s</td>
                      <td className="py-2">{inc.auto_resolved ? '✅' : '❌'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
