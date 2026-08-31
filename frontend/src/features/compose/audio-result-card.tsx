import { useEffect, useState } from 'react'
import { Download, Pause, Play, RotateCcw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { SynthResult } from '../../api/types'
import { Button } from '../../components/ui/button'
import { downloadAudio } from '../../lib/download'
import { useAudioPlayer } from './use-audio-player'
import { appConfig } from '../../config/app-config'
import type { SynthParams } from '../../api/types'
import { defaultSubtitleOptions } from '../../lib/subtitle/conventions'
import { useGenerateSubtitle } from './use-generate-subtitle'
import { LimitStates } from '../status/limit-states'

export function AudioResultCard({ result, params, onRegenerate }: { result: SynthResult; params: SynthParams; onRegenerate(): void }) {
  const { t } = useTranslation()
  const player = useAudioPlayer()
  const subtitle = useGenerateSubtitle()
  const [subtitleOptions, setSubtitleOptions] = useState(defaultSubtitleOptions)

  useEffect(() => {
    return () => {
      if (result.audioUrl.startsWith('blob:')) {
        URL.revokeObjectURL(result.audioUrl)
      }
    }
  }, [result.audioUrl])

  return (
    <section className="rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] p-4">
      <h2 className="font-semibold">{t('compose.result')}</h2>
      {result.previewOnly && <p className="mt-1 text-xs text-[var(--color-muted)]">{t('compose.mp3Preview')}</p>}

      <audio
        ref={player.audioRef}
        src={result.audioUrl}
        onPlay={player.markPlaying}
        onPause={player.stop}
        onEnded={player.stop}
        className="mt-3 w-full"
        controls
        preload="metadata"
      />

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <Button variant="secondary" onClick={() => void player.toggle()}>
          {player.playing ? (
            <>
              <Pause className="shrink-0" size={16} fill="currentColor" />
              <span>{t('compose.pause')}</span>
            </>
          ) : (
            <>
              <Play className="shrink-0" size={16} fill="currentColor" />
              <span>{t('compose.play')}</span>
            </>
          )}
        </Button>
        <Button variant="secondary" onClick={() => downloadAudio(result.audioUrl, result.filename)}>
          <Download className="shrink-0" size={16} />
          <span>{t('compose.download')}</span>
        </Button>
        <Button variant="quiet" onClick={onRegenerate}>
          <RotateCcw className="shrink-0" size={16} />
          <span>{t('compose.regenerate')}</span>
        </Button>
        {appConfig.features.ttsToSrt && (
          <Button variant="secondary" disabled={subtitle.state === 'generating'} onClick={() => void subtitle.generate({ result, params, options: subtitleOptions })}>
            <span>{t('compose.subtitle')}</span>
          </Button>
        )}
      </div>
      {appConfig.features.ttsToSrt && <section className="mt-4 rounded-[var(--radius-control)] border border-[var(--color-border)] p-3"><p className="text-sm leading-6 text-[var(--color-muted)]">{result.engine === 'voicevox' ? t('compose.subtitleNative') : t('compose.subtitleApproximate')}</p><div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="grid gap-1 text-sm font-medium">{t('transcribe.charsPerLine')}<input className="min-h-11 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 text-base font-normal md:text-sm" type="number" min="20" max="60" value={subtitleOptions.maxCharsPerLine} onChange={event => setSubtitleOptions(current => ({ ...current, maxCharsPerLine: Number(event.target.value) }))} /></label><label className="grid gap-1 text-sm font-medium">{t('transcribe.linesPerCue')}<input className="min-h-11 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 text-base font-normal md:text-sm" type="number" min="1" max="2" value={subtitleOptions.maxLinesPerCue} onChange={event => setSubtitleOptions(current => ({ ...current, maxLinesPerCue: Number(event.target.value) }))} /></label></div>{subtitle.state === 'generating' && <div className="mt-3 flex items-center gap-3"><span role="status" className="text-sm font-medium">{t('compose.subtitleGenerating')}</span><Button variant="quiet" onClick={subtitle.cancel}>{t('action.cancel')}</Button></div>}{subtitle.state === 'error' && <div className="mt-3 flex flex-wrap items-center gap-3"><LimitStates kind={subtitle.error && subtitle.error !== 'generic' ? subtitle.error : null} /><Button variant="secondary" onClick={subtitle.retry}>{t('action.retry')}</Button></div>}{subtitle.state === 'success' && <p className="mt-3 text-sm text-[var(--color-primary)]">{t('compose.subtitleDownloaded')}</p>}</section>}
    </section>
  )
}
