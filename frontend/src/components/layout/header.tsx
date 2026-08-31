import { CircleHelp, Sliders } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LanguageToggle } from '../ui/language-toggle'
import { ThemeToggle } from '../ui/theme-toggle'
import { FeatureNav } from './feature-nav'
import { SupportDialog } from '../../features/support/support-dialog'
import { LiveBadge } from '../../features/status/live-badge'

export function Header({ activeUsers = null }: { activeUsers?: number | null }) {
  const { t } = useTranslation()
  const [supportOpen, setSupportOpen] = useState(false)

  return (
    <>
      <header className="relative z-20 border-b border-[var(--color-border)] bg-[var(--color-bg)] pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center gap-2 px-4 sm:px-6">
          <a href="/" className="mr-2 shrink-0 text-base font-bold tracking-[-0.02em] text-[var(--color-text)]">
            {t('app.name')}
          </a>
          <FeatureNav />
          <div className="ml-auto flex items-center gap-1">
            <LiveBadge count={activeUsers} />
            <span className="hidden rounded-full bg-[var(--color-primary-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--color-primary)] xl:inline-flex">
              {t('shell.voiceLanguage')}
            </span>
            <button
              type="button"
              onClick={() => setSupportOpen(true)}
              className="hidden min-h-11 cursor-pointer items-center gap-1.5 px-2.5 text-sm font-medium text-[var(--color-muted)] hover:text-[var(--color-text)] md:flex focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]"
            >
              <CircleHelp className="shrink-0 text-[var(--color-primary)]" size={17} />
              <span>{t('shell.help')}</span>
            </button>
            <button
              type="button"
              onClick={() => setSupportOpen(true)}
              className="hidden min-h-11 cursor-pointer items-center gap-1.5 px-2.5 text-sm font-medium text-[var(--color-muted)] hover:text-[var(--color-text)] md:flex focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]"
            >
              <Sliders className="shrink-0 text-[var(--color-primary)]" size={17} />
              <span>{t('shell.serverInfo')}</span>
            </button>
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <SupportDialog open={supportOpen} onClose={() => setSupportOpen(false)} />
    </>
  )
}
