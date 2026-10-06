import type { ReactNode } from 'react';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  trend?: 'up' | 'down' | 'neutral';
}

export function KpiCard({ title, value, subtitle, icon }: KpiCardProps) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800 p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-400">{title}</p>
          <p className="mt-1 text-2xl font-bold text-white">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {icon && (
          <div className="ml-4 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-400">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
