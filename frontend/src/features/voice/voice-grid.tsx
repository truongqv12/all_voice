import type { Voice } from '../../api/types'
import { EmptyState } from '../../components/ui/empty-state'
import { Button } from '../../components/ui/button'
import { Skeleton } from '../../components/ui/skeleton'
import { useTranslation } from 'react-i18next'
import { useSelection } from '../../store/selection'
import { useVoicePreview } from './use-voice-preview'
import { VoiceCard } from './voice-card'

interface Props { voices: Voice[]; loading: boolean; error: boolean; onRetry(): void; onReset(): void; onSelected?(): void }
export function VoiceGrid({ voices, loading, error, onRetry, onReset, onSelected }: Props) {
  const { selectedVoice, selectVoice } = useSelection()
  const preview = useVoicePreview()
  const { t } = useTranslation()
  if (loading) return <div className="grid gap-3">{[1, 2, 3, 4].map(index => <Skeleton key={index} className="h-48" />)}</div>
  if (error) return <EmptyState title={t('voice.loadErrorTitle')} description={t('voice.loadErrorDescription')} action={<Button variant="secondary" onClick={onRetry}>{t('voice.retry')}</Button>} />
  if (!voices.length) return <EmptyState title={t('voice.emptyTitle')} description={t('voice.emptyDescription')} action={<Button variant="secondary" onClick={onReset}>{t('voice.resetAction')}</Button>} />
  const yours = voices.filter(voice => voice.engine === 'clone'); const catalog = voices.filter(voice => voice.engine !== 'clone')
  const cards = (items: Voice[]) => items.map(voice => <VoiceCard key={voice.id} voice={voice} selected={voice.id === selectedVoice?.id} active={preview.activeId === voice.id} loading={preview.loadingId === voice.id} onToggle={() => void preview.toggle(voice)} onSelect={() => { selectVoice(voice); onSelected?.() }} />)
  return <div className="space-y-3">{yours.length > 0 && <section><h3 className="mb-2 text-sm font-semibold text-[var(--color-primary)]">{t('voice.yours')}</h3><div className="grid gap-3">{cards(yours)}</div></section>}<div className="grid gap-3">{cards(catalog)}</div></div>
}
