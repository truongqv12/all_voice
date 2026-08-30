import { Clock3 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { TranscriptionResult } from '../../api/transcribe-api'
import { useTranscriptPlayback } from './use-transcript-playback'

function time(seconds: number) { return `00:${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}` }

export function TranscriptPanel({ result, audioUrl }: { result: TranscriptionResult; audioUrl: string | null }) {
  const { t } = useTranslation(); const player = useTranscriptPlayback()
  return <section className="rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-6"><div className="flex flex-wrap items-baseline justify-between gap-2"><div><p className="text-xs font-bold tracking-[0.08em] text-[var(--color-primary)]">{t('transcribe.sampleData')}</p><h2 className="mt-1 text-xl font-bold">{t('transcribe.transcript')}</h2></div><span className="text-sm text-[var(--color-muted)]">{t(`transcribe.language.${result.language}`)}</span></div>{audioUrl && <audio ref={player.audioRef} src={audioUrl} controls preload="metadata" onTimeUpdate={player.onTimeUpdate} className="mt-4 w-full" />}<ol className="mt-5 space-y-2">{result.segments.map(segment => { const active = player.currentTime >= segment.start && player.currentTime <= segment.end; return <li key={segment.id} className={`rounded-[var(--radius-control)] border p-3 transition-colors ${active ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]' : 'border-transparent bg-[var(--color-surface-soft)]'}`}><div className="flex gap-2"><Clock3 className="mt-0.5 shrink-0 text-[var(--color-muted)]" size={15} /><span className="text-xs tabular-nums text-[var(--color-muted)]">{time(segment.start)}</span><p className="leading-6">{segment.text}</p></div></li> })}</ol></section>
}
