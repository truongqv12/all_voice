import { AlertTriangle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { LimitKind } from '../../lib/limits'

export function LimitStates({ kind }: { kind: LimitKind | null }) {
  const { t } = useTranslation()
  if (!kind) return null
  return <p role="alert" className="flex items-start gap-2 rounded-[var(--radius-control)] border border-[var(--color-warning)] bg-[var(--color-surface-soft)] p-3 text-sm leading-6"><AlertTriangle className="mt-0.5 shrink-0 text-[var(--color-warning)]" size={17} /><span><strong>{t(`limits.${kind}.title`)}</strong><br />{t(`limits.${kind}.description`)}</span></p>
}
