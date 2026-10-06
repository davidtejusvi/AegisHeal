import clsx from 'clsx';

export function StatusDot({ healthy }: { healthy: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={clsx(
          'inline-block h-2.5 w-2.5 rounded-full',
          healthy ? 'bg-green-400 shadow-[0_0_6px_#4ade80]' : 'bg-red-500 shadow-[0_0_6px_#ef4444]'
        )}
      />
      <span className={clsx('text-sm font-medium', healthy ? 'text-green-400' : 'text-red-400')}>
        {healthy ? 'Healthy' : 'Unhealthy'}
      </span>
    </span>
  );
}
