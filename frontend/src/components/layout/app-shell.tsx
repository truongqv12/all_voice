import { Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { FeatureNav } from './feature-nav'
import { Footer } from './footer'
import { Header } from './header'

export function AppShell() {
  const { t } = useTranslation()
  return (
    <div className="min-h-dvh bg-[var(--color-bg)] text-[var(--color-text)]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[var(--color-surface)] focus:px-3 focus:py-2"
      >
        {t('a11y.skipToContent')}
      </a>
      <Header />
      <div className="border-b border-[var(--color-border)] bg-[var(--color-surface)] lg:hidden">
        <FeatureNav mobile />
      </div>
      <main id="main" className="mx-auto min-h-[calc(100dvh-8rem)] max-w-7xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
