import { ChevronDown } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useSelection } from '../../store/selection'
import { FlagIcon } from '../../components/ui/flag-icon'

export function SelectedVoiceChip({ onOpen }: { onOpen(): void }) {
  const { selectedVoice, style } = useSelection()
  const { t } = useTranslation()
  if (!selectedVoice) return null
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex min-h-11 w-full min-w-0 cursor-pointer items-center gap-3 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-left transition-colors hover:bg-[var(--color-surface-soft)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid lg:cursor-default lg:hover:bg-[var(--color-surface)]"
      aria-label={t('voice.change')}
    >
      <FlagIcon country={selectedVoice.language} className="size-4.5 rounded-xs" />
      <span className="min-w-0 grow leading-snug">
        <span className="text-sm font-semibold whitespace-normal break-words">
          {selectedVoice.engine === 'voicevox' && <span className="text-[var(--color-primary)]">[{selectedVoice.id}] </span>}
          {selectedVoice.name}
        </span>
        <span className="text-sm text-[var(--color-muted)] font-normal ml-1 whitespace-normal break-words">
          ({t(`voice.${selectedVoice.gender}`)}{selectedVoice.age ? ` · ${selectedVoice.age}` : ''}{style ? ` · ${style}` : ''})
        </span>
      </span>
      <ChevronDown size={18} className="shrink-0 text-[var(--color-muted)] lg:hidden" />
    </button>
  )
}
