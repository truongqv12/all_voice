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
      className="flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-left transition-colors hover:bg-[var(--color-surface-soft)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid lg:cursor-default lg:hover:bg-[var(--color-surface)]"
      aria-label={t('voice.change')}
    >
      <FlagIcon country={selectedVoice.language} className="size-4.5 rounded-xs" />
      <span className="min-w-0 grow">
        <span className="block truncate text-sm font-semibold">{selectedVoice.name}</span>
        <span className="block truncate text-xs text-[var(--color-muted)]">{selectedVoice.engine} · {t(`voice.${selectedVoice.gender}`)} · {style}</span>
      </span>
      <ChevronDown size={18} className="shrink-0 text-[var(--color-muted)] lg:hidden" />
    </button>
  )
}
