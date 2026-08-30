import { AudioLines, FileAudio, ScanText } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

const items = [
  { to: '/', key: 'nav.tts', Icon: AudioLines, end: true },
  { to: '/transcribe', key: 'nav.transcribe', Icon: ScanText },
  { to: '/clone', key: 'nav.clone', Icon: FileAudio },
]

export function FeatureNav({ mobile = false }: { mobile?: boolean }) {
  const { t } = useTranslation()
  const indicator = mobile ? 'border-t-2' : 'border-b-2'
  return <nav aria-label={t('a11y.featureNavigation')} className={mobile ? 'grid grid-cols-3' : 'hidden items-center gap-1 lg:flex'}>{items.map(({ to, key, Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex min-h-11 min-w-0 items-center justify-center gap-2 border-transparent px-2 text-center text-xs font-semibold transition-colors ${indicator} ${isActive ? 'border-current text-[var(--color-primary)]' : 'text-[var(--color-muted)] hover:text-[var(--color-text)]'} ${mobile ? 'flex-col py-1' : 'rounded-[var(--radius-control)] whitespace-nowrap'}`}><Icon size={mobile ? 18 : 17} strokeWidth={1.8} /><span className={mobile ? 'leading-tight' : ''}>{t(key)}</span></NavLink>)}</nav>
}
