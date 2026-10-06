import clsx from 'clsx';
import type { Severity } from '../api/types';

const SEVERITY_STYLES: Record<Severity, string> = {
  LOW: 'bg-green-400/10 text-green-400 ring-1 ring-green-400/20',
  MEDIUM: 'bg-yellow-400/10 text-yellow-400 ring-1 ring-yellow-400/20',
  HIGH: 'bg-orange-400/10 text-orange-400 ring-1 ring-orange-400/20',
  CRITICAL: 'bg-red-500/10 text-red-400 ring-1 ring-red-400/20',
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide',
        SEVERITY_STYLES[severity]
      )}
    >
      {severity}
    </span>
  );
}
