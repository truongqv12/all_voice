export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-[var(--radius-control)] bg-[var(--color-surface-soft)] ${className}`} aria-hidden="true" />
}
