import type { ReactNode } from 'react'

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="rounded-[var(--radius-control)] border border-dashed border-[var(--color-border)] p-5 text-center"><h3 className="font-semibold">{title}</h3><p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-[var(--color-muted)]">{description}</p>{action && <div className="mt-4">{action}</div>}</div>
}
