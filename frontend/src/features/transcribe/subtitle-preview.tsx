import type { SubtitleCue } from '../../lib/subtitle/chunk-cues'
import { useTranslation } from 'react-i18next'

export function SubtitlePreview({ cues }: { cues: SubtitleCue[] }) {
  const { t } = useTranslation()
  return <div className="mt-4 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg)] p-3.5"><p className="text-xs font-bold tracking-[0.08em] text-[var(--color-muted)]">{t('transcribe.preview')}</p><ol className="mt-2.5 space-y-2">{cues.slice(0, 3).map((cue, index) => <li key={`${cue.start}-${index}`} className="flex items-start gap-2.5 text-sm leading-5"><span className="shrink-0 rounded bg-[var(--color-surface-soft)] px-1.5 py-0.5 font-mono text-xs tabular-nums text-[var(--color-muted)]">{cue.start.toFixed(2)}{t('transcribe.seconds')}</span><div className="min-w-0 flex-1">{cue.lines.map(line => <p key={line} className="break-words">{line}</p>)}</div></li>)}</ol></div>
}
