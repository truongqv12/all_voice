import { useTranslation } from 'react-i18next'
import { appConfig } from '../../config/app-config'

export function Footer() {
  const { t } = useTranslation()
  return <footer className="border-t border-[var(--color-border)]"><div className="mx-auto max-w-7xl px-4 py-5 text-sm text-[var(--color-muted)] sm:px-6">{t(appConfig.useMock ? 'footer.mock' : 'footer.live')}</div></footer>
}
