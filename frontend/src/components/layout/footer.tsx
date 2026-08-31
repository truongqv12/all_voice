import { useTranslation } from 'react-i18next'
import { appConfig } from '../../config/app-config'
import { formatCount } from '../../lib/format-count'

export function Footer({ totalUsers = null }: { totalUsers?: number | null }) {
  const { t, i18n } = useTranslation()
  return (
    <footer className="border-t border-[var(--color-border)]">
      <div className="mx-auto max-w-7xl px-4 py-5 text-sm text-[var(--color-muted)] sm:px-6">
        {t(appConfig.useMock ? 'footer.mock' : 'footer.live')}
        {totalUsers !== null && (
          <span> · {t('stats.total', { display: formatCount(totalUsers, i18n.language) })}</span>
        )}
      </div>
    </footer>
  )
}
