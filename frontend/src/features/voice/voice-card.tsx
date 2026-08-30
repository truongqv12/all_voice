import { Check } from 'lucide-react'
import { memo } from 'react'
import { useTranslation } from 'react-i18next'
import type { Voice } from '../../api/types'
import { Button } from '../../components/ui/button'
import { FlagIcon } from '../../components/ui/flag-icon'
import { VoicePreviewButton } from './voice-preview-button'

export const VoiceCard = memo(function VoiceCard({
  voice,
  selected,
  active,
  loading,
  onSelect,
  onToggle,
}: {
  voice: Voice
  selected: boolean
  active: boolean
  loading: boolean
  onSelect(): void
  onToggle(): void
}) {
  const { t } = useTranslation()

  return (
    <article
      style={{ contentVisibility: 'auto', containIntrinsicSize: '140px' }}
      className={`rounded-[var(--radius-control)] border p-3.5 transition-colors duration-150 ${
        selected
          ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
          : 'border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-muted)]'
      }`}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 grow">
          <h3 className="truncate text-sm font-semibold">{voice.name}</h3>
        </div>
        <VoicePreviewButton voice={voice} active={active} loading={loading} onToggle={onToggle} />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-[var(--color-muted)]">
        <FlagIcon country={voice.language} className="size-3.5 shrink-0 rounded-xs" />
        <span className="font-medium text-[var(--color-text)]">{voice.engine}</span>
        {voice.styles.length > 0 && (
          <>
            <span aria-hidden="true">·</span>
            <span>{voice.styles[0]}</span>
          </>
        )}
      </div>
      <Button
        variant={selected ? 'secondary' : 'quiet'}
        className="mt-3 w-full"
        onClick={onSelect}
      >
        {selected ? (
          <>
            <Check className="shrink-0" size={15} />
            <span>{t('voice.selected')}</span>
          </>
        ) : (
          <span>{t('voice.select')}</span>
        )}
      </Button>
    </article>
  )
})
