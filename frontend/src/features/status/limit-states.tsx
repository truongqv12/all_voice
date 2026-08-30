import { AlertTriangle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { appConfig } from '../../config/app-config'

type Demo = 'rate' | 'quota' | 'too-long'
function demo(): Demo | null { const value = new URLSearchParams(window.location.search).get('limit'); return value === 'rate' || value === 'quota' || value === 'too-long' ? value : null }

export function LimitStates() {
  const { t } = useTranslation(); const state = appConfig.demos.limits ? demo() : null
  if (!state) return null
  return <p role="alert" className="flex items-start gap-2 rounded-[var(--radius-control)] border border-[var(--color-warning)] bg-[var(--color-surface-soft)] p-3 text-sm leading-6"><AlertTriangle className="mt-0.5 shrink-0 text-[var(--color-warning)]" size={17} /><span><strong>{t(`limits.${state}.title`)}</strong><br />{t(`limits.${state}.description`)}</span></p>
}
