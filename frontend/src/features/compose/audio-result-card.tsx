import { useEffect } from 'react'
import { Download, Pause, Play, RotateCcw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { SynthResult } from '../../api/types'
import { Button } from '../../components/ui/button'
import { Tooltip } from '../../components/ui/tooltip'
import { downloadAudio } from '../../lib/download'
import { useAudioPlayer } from './use-audio-player'
import { appConfig } from '../../config/app-config'

export function AudioResultCard({ result, onRegenerate }: { result: SynthResult; onRegenerate(): void }) {
  const { t } = useTranslation()
  const player = useAudioPlayer()

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
          <Tooltip label={t('compose.subtitleSoon')}>
            <span>
              <Button variant="secondary" disabled>
                <span>{t('compose.subtitle')}</span>
              </Button>
            </span>
          </Tooltip>
        )}
      </div>
    </section>
  )
}
