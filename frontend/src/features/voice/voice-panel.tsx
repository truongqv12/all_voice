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
    <section aria-label={t('voice.title')} className="space-y-4">
      <VoiceFilterBar {...filters} />
      <VoiceGrid
        voices={shownVoices}
        loading={loading}
        error={error || demoError}
        onRetry={() => void reload()}
        onReset={filters.reset}
        onSelected={onSelected}
      />
    </section>
  )
}
