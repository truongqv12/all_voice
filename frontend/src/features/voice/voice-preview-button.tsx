import { LoaderCircle, Pause, Play } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Voice } from '../../api/types'
import { IconButton } from '../../components/ui/icon-button'

export function VoicePreviewButton({ voice, active, loading, onToggle }: { voice: Voice; active: boolean; loading: boolean; onToggle(): void }) {
  const { t } = useTranslation()
  const label = active ? t('voice.pause', { name: voice.name }) : t('voice.preview', { name: voice.name })
  return <IconButton size="sm" onClick={onToggle} aria-label={label} disabled={loading}>{loading ? <LoaderCircle className="animate-spin" size={16} /> : active ? <Pause size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}</IconButton>
}
