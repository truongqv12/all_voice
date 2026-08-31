import { useTranslation } from 'react-i18next'
import { AudioDropZone } from './audio-drop-zone'
import { SubtitleExportPanel } from './subtitle-export-panel'
import { TranscriptPanel } from './transcript-panel'
import { useTranscribe } from './use-transcribe'

import { LimitStates } from '../status/limit-states'
import type { LimitKind } from '../../lib/limits'
import { Button } from '../../components/ui/button'

export default function TranscribePage() {
  const { t } = useTranslation(); const transcribe = useTranscribe()
  const isWorking = transcribe.state === 'uploading' || transcribe.state === 'transcribing'
  return <div className="mx-auto max-w-5xl space-y-5"><section className="max-w-2xl"><p className="text-xs font-bold tracking-[0.08em] text-[var(--color-primary)]">{t('transcribe.eyebrow')}</p><h1 className="mt-2 text-balance text-3xl font-bold tracking-[-0.03em] sm:text-4xl">{t('transcribe.title')}</h1><p className="mt-3 max-w-xl leading-7 text-[var(--color-muted)]">{t('transcribe.description')}</p></section><LimitStates kind={['format', 'size', 'generic', ''].includes(transcribe.error as string) ? null : transcribe.error as LimitKind} />{!transcribe.result && <AudioDropZone disabled={isWorking} onFile={file => void transcribe.transcribe(file)} error={['format', 'size', 'generic'].includes(transcribe.error as string) ? (transcribe.error as string) : ''} />}{transcribe.state === 'error' && <Button variant="secondary" onClick={transcribe.retry}>{t('action.retry')}</Button>}{isWorking && <section aria-live="polite" className="rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5"><div className="flex justify-between gap-4"><p className="font-semibold">{t(`transcribe.progress.${transcribe.state}`)}</p><span className="tabular-nums text-[var(--color-muted)]">{transcribe.progress > 0 ? `${transcribe.progress}%` : t('compose.preparing')}</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--color-surface-soft)]"><div className={`h-full bg-[var(--color-primary)] ${transcribe.progress > 0 ? 'transition-[width]' : 'w-1/2 animate-pulse'}`} style={transcribe.progress > 0 ? { width: `${transcribe.progress}%` } : undefined} /></div><div className="mt-4"><Button variant="secondary" onClick={transcribe.cancel}>{t('action.cancel')}</Button></div></section>}{transcribe.result && <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,.72fr)]"><TranscriptPanel result={transcribe.result} audioUrl={transcribe.audioUrl} /><SubtitleExportPanel result={transcribe.result} filename={transcribe.file?.name ?? 'transcript.mp3'} /></div>}</div>
}
