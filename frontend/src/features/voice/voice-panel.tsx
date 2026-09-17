import { useVoiceFilters } from './use-voice-filters'
import { VoiceFilterBar } from './voice-filter-bar'
import { VoiceGrid } from './voice-grid'
import { useTranslation } from 'react-i18next'
import { useSelection } from '../../store/selection'

export function VoicePanel({ onSelected }: { onSelected?(): void }) {
  const { voices, loading, error, reload } = useSelection()
  const filters = useVoiceFilters(voices)
  const { t } = useTranslation()
  const demo = new URLSearchParams(window.location.search).get('voiceState')
  const demoError = demo === 'error'
  const shownVoices = demo === 'empty' ? [] : filters.filtered
  return (
    <section aria-label={t('voice.title')} className="flex flex-col gap-4 min-h-0 h-full">
      <div className="shrink-0">
        <VoiceFilterBar {...filters} />
      </div>
      <div className="flex-1 overflow-y-auto pr-2 -mr-2 min-h-0 pb-4">
        <VoiceGrid
          voices={shownVoices}
          loading={loading}
          error={error || demoError}
          onRetry={() => void reload()}
          onReset={filters.reset}
          onSelected={onSelected}
        />
      </div>
    </section>
  )
}
