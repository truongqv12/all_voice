export function Toast({ message }: { message: string }) {
  return <p className="rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-muted)]" role="status" aria-live="polite">{message}</p>
}
