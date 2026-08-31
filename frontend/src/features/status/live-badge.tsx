import { useTranslation } from 'react-i18next'
import { formatCount } from '../../lib/format-count'

/**
 * Header pill showing how many people are using the app right now ("đang dùng").
 * Presentational — the poll lives in `useLiveStats`, lifted to AppShell so the
 * header pill and footer total share one poller. Renders nothing until the
 * first value arrives, so there is no flash of an empty badge.
 */
export function LiveBadge({ count }: { count: number | null }) {
  const { t, i18n } = useTranslation()
  if (count === null) return null
  return (
    <span
      className="hidden items-center gap-1.5 rounded-full bg-[var(--color-primary-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--color-primary)] sm:inline-flex"
      aria-live="polite"
    >
      <span className="relative flex h-2 w-2" aria-hidden="true">
        {/* animate-ping is neutralised under prefers-reduced-motion (global.css). */}
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--color-success)] opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--color-success)]" />
      </span>
      {t('stats.active', { display: formatCount(count, i18n.language) })}
    </span>
  )
}
