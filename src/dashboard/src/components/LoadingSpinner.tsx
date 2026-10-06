export function LoadingSpinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizeClass = { sm: 'h-4 w-4', md: 'h-8 w-8', lg: 'h-12 w-12' }[size];
  return (
    <div className="flex items-center justify-center p-4">
      <div
        className={`${sizeClass} animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400`}
        role="status"
        aria-label="Loading"
      />
    </div>
  );
}
