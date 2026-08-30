import { textLimits } from '../../lib/limits'
import { useTranslation } from 'react-i18next'

export function CharCounter({ count }: { count: number }) {
  const { t } = useTranslation(); const over = count > textLimits.hard; const stream = count > textLimits.soft
  return <div className={`mt-2 text-sm tabular-nums ${over ? 'text-[var(--color-danger)]' : stream ? 'text-[var(--color-warning)]' : 'text-[var(--color-muted)]'}`}><p>{t('compose.counter', { count, limit: textLimits.hard.toLocaleString() })}</p>{over ? <p className="mt-1">{t('compose.hardLimit')}</p> : stream ? <p className="mt-1">{t('compose.streamMode')}</p> : null}</div>
}
