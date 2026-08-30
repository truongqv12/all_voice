import { useTranslation } from 'react-i18next'
import { FlagIcon } from './flag-icon'

export function LanguageToggle() {
  const { i18n, t } = useTranslation()
  const isVietnamese = i18n.resolvedLanguage !== 'en'
  return (
    <button
      type="button"
      onClick={() => void i18n.changeLanguage(isVietnamese ? 'en' : 'vi')}
      aria-label={t('language.switch')}
      className="flex min-h-11 cursor-pointer items-center gap-1.5 rounded-[var(--radius-control)] px-2 text-xs font-bold text-[var(--color-muted)] transition-colors hover:bg-[var(--color-surface-soft)] hover:text-[var(--color-text)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid active:scale-[0.98]"
    >
      <FlagIcon country={isVietnamese ? 'vi' : 'en'} className="size-4 rounded-xs" />
      <span>{isVietnamese ? 'VI' : 'EN'}</span>
    </button>
  )
}
