import { LogIn } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/button'

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation(); const [signedIn, setSignedIn] = useState(false)
  if (signedIn) return <>{children}</>
  return <section className="max-w-2xl rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] p-6 sm:p-8"><p className="text-xs font-bold tracking-[0.08em] text-[var(--color-primary)]">{t('clone.demo')}</p><h2 className="mt-2 text-2xl font-bold">{t('clone.authTitle')}</h2><p className="mt-3 max-w-xl leading-7 text-[var(--color-muted)]">{t('clone.authDescription')}</p><Button className="mt-5" onClick={() => setSignedIn(true)}><LogIn className="mr-2" size={17} />{t('clone.signIn')}</Button></section>
}
