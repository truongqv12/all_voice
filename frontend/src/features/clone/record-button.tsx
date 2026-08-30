import { Mic, Square } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/button'

export function RecordButton({ onReady }: { onReady(name: string): void }) {
  const { t } = useTranslation()
  const [seconds, setSeconds] = useState(0)
  const recording = seconds > 0 && seconds < 10

  useEffect(() => {
    if (!recording) return
    const id = window.setInterval(() => {
      setSeconds(current => {
        if (current >= 10) return current
        return current + 1
      })
    }, 1000)
    return () => window.clearInterval(id)
  }, [recording])

  useEffect(() => {
    if (seconds === 10) {
      onReady(t('clone.recordingReady'))
    }
  }, [seconds, onReady, t])

  function toggle() {
    if (recording) {
      if (seconds >= 2) {
        onReady(`${t('clone.recordingReady')} (${seconds}s)`)
      }
      setSeconds(0)
      return
    }
    setSeconds(1)
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="secondary" onClick={toggle}>
        {recording ? (
          <>
            <Square className="shrink-0 text-[var(--color-danger)]" size={16} />
            <span>{t('clone.stopRecording')}</span>
          </>
        ) : (
          <>
            <Mic className="shrink-0" size={16} />
            <span>{t('clone.recordSample')}</span>
          </>
        )}
      </Button>
      {recording && <span aria-live="polite" className="text-sm tabular-nums text-[var(--color-muted)]">{seconds}/10s</span>}
      {seconds === 10 && <span className="text-sm text-[var(--color-primary)]">{t('clone.recordingReady')}</span>}
    </div>
  )
}
