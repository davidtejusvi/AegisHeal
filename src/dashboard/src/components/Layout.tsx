import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Activity, AlertTriangle, Home, Menu, Server, Shield, X } from 'lucide-react';
import clsx from 'clsx';
import { useAnomalyHealth, useRemediationHealth } from '../hooks/useHealth';
import { StatusDot } from './StatusDot';
import { format } from 'date-fns';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: Home, end: true },
  { to: '/anomalies', label: 'Anomalies', icon: Activity, end: false },
  { to: '/incidents', label: 'Incidents', icon: AlertTriangle, end: false },
  { to: '/services', label: 'Services', icon: Server, end: false },
];

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const anomalyHealth = useAnomalyHealth();
  const remediationHealth = useRemediationHealth();

  const anomalyOk = anomalyHealth.data?.status === 'healthy';
  const remediationOk = remediationHealth.data?.status === 'healthy';
  const bothOk = anomalyOk && remediationOk;
  const noneOk = !anomalyOk && !remediationOk;

  const overallStatus = noneOk ? 'CRITICAL' : !bothOk ? 'DEGRADED' : 'HEALTHY';
  const overallColor = noneOk ? 'text-red-400 bg-red-400/10' : !bothOk ? 'text-yellow-400 bg-yellow-400/10' : 'text-green-400 bg-green-400/10';

  const now = new Date();

  const Sidebar = ({ mobile }: { mobile?: boolean }) => (
    <aside
      className={clsx(
        'flex flex-col',
        mobile
          ? 'fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 border-r border-slate-700 p-4'
          : 'hidden lg:flex w-64 flex-shrink-0 border-r border-slate-700 bg-slate-900 p-4'
      )}
    >
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-400">
          <Shield className="h-5 w-5 text-slate-900" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-white">AegisHeal</h1>
          <p className="text-xs text-slate-400">AI Self-Healing Infra</p>
        </div>
        {mobile && (
          <button
            onClick={() => setSidebarOpen(false)}
            className="ml-auto text-slate-400 hover:text-white"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-cyan-400/10 text-cyan-400'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              )
            }
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-4 rounded-lg border border-slate-700 bg-slate-800 p-3 text-xs">
        <p className="text-slate-400 mb-1">Services</p>
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-slate-300">Anomaly Det.</span>
            <StatusDot healthy={anomalyOk} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-300">Remediation</span>
            <StatusDot healthy={remediationOk} />
          </div>
        </div>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-slate-900 text-slate-100">
      <Sidebar />
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
          <Sidebar mobile />
        </>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-slate-700 bg-slate-900 px-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden text-slate-400 hover:text-white"
            aria-label="Open sidebar"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-3 ml-auto">
            <span className="text-xs text-slate-500">
              Updated {format(now, 'HH:mm:ss')}
            </span>
            <span
              className={clsx(
                'rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide',
                overallColor
              )}
            >
              {overallStatus}
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
