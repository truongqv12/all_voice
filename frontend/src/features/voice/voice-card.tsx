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
  previewUnavailable,
  onSelect,
  onToggle,
}: {
  voice: Voice
  selected: boolean
  active: boolean
  loading: boolean
  previewUnavailable: boolean
  onSelect(): void
  onToggle(): void
}) {
  const { t } = useTranslation()

  return (
    <article
      style={{ contentVisibility: 'auto', containIntrinsicSize: '100px' }}
      className={`min-w-0 overflow-hidden rounded-[var(--radius-control)] border p-2.5 transition-colors duration-150 ${
        selected
          ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
          : 'border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-muted)]'
      }`}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 grow">
          <h3 className="text-sm font-semibold whitespace-normal break-words leading-tight">
            {voice.engine === 'voicevox' && <span className="text-[var(--color-primary)]">[{voice.id}] </span>}
            {voice.name}
          </h3>
        </div>
        <VoicePreviewButton voice={voice} active={active} loading={loading} onToggle={onToggle} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--color-muted)]">
        <FlagIcon country={voice.language} className="size-3 shrink-0 rounded-xs" />
        <span className="font-medium text-[var(--color-text)]">{voice.engine}</span>
        <span aria-hidden="true">·</span>
        <span>{t(`voice.${voice.gender}`)} {voice.age ? ` (${voice.age})` : ''}</span>
        {voice.styles.length > 0 && (
          <>
            <span aria-hidden="true">·</span>
            <span>{voice.styles[0]}</span>
          </>
        )}
      </div>
      <Button
        size="sm"
        variant={selected ? 'secondary' : 'quiet'}
        className="mt-2.5 w-full"
        onClick={onSelect}
      >
        {selected ? (
          <>
            <Check className="shrink-0" size={14} />
            <span>{t('voice.selected')}</span>
          </>
        ) : (
          <span>{t('voice.select')}</span>
        )}
      </Button>
      {previewUnavailable && <p role="alert" className="mt-1.5 text-[11px] leading-snug text-[var(--color-warning)]">{t('voice.previewUnavailable')}</p>}
    </article>
  )
})
