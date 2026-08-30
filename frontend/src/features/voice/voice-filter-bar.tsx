import { Globe, RotateCcw, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { VoiceGender, VoiceLanguage } from '../../api/types'
import { Chip } from '../../components/ui/chip'
import { FlagIcon } from '../../components/ui/flag-icon'
import { IconButton } from '../../components/ui/icon-button'

interface Props {
  language: VoiceLanguage | 'all'
  gender: VoiceGender | 'all'
  query: string
  setLanguage(value: VoiceLanguage | 'all'): void
  setGender(value: VoiceGender | 'all'): void
  setQuery(value: string): void
  reset(): void
}

export function VoiceFilterBar({ language, gender, query, setLanguage, setGender, setQuery, reset }: Props) {
  const { t } = useTranslation()
  const languages: Array<{ value: VoiceLanguage | 'all'; label: string; country: 'vi' | 'en' | 'ja' | 'all' }> = [
    { value: 'all', label: t('voice.all'), country: 'all' },
    { value: 'vi', label: 'Tiếng Việt', country: 'vi' },
    { value: 'en', label: 'English', country: 'en' },
    { value: 'ja', label: '日本語', country: 'ja' },
  ]
  const genders: Array<{ value: VoiceGender | 'all'; label: string }> = [
    { value: 'all', label: t('voice.allGroups') },
    { value: 'female', label: t('voice.female') },
    { value: 'male', label: t('voice.male') },
    { value: 'neutral', label: t('voice.neutral') },
  ]

  return (
    <div className="space-y-3">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {languages.map(item => (
          <Chip key={item.value} selected={language === item.value} onClick={() => setLanguage(item.value)} className="flex items-center gap-1.5 whitespace-nowrap">
            {item.country !== 'all' ? (
              <FlagIcon country={item.country} className="size-3.5 rounded-xs" />
            ) : (
              <Globe size={14} className="shrink-0 text-[var(--color-muted)]" />
            )}
            <span>{item.label}</span>
          </Chip>
        ))}
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {genders.map(item => (
          <Chip key={item.value} selected={gender === item.value} onClick={() => setGender(item.value)}>
            {item.label}
          </Chip>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <label className="relative min-w-0 grow">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-muted)]" size={18} />
          <input
            value={query}
            onChange={event => setQuery(event.target.value)}
            className="min-h-11 w-full rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] py-2 pl-10 pr-3 text-base text-[var(--color-text)] placeholder:text-[var(--color-muted)] focus-visible:border-[var(--color-primary)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid"
            placeholder={t('voice.search')}
          />
        </label>
        <IconButton onClick={reset} aria-label={t('voice.reset')}>
          <RotateCcw size={18} />
        </IconButton>
      </div>
    </div>
  )
}
