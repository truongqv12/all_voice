import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { AudioFormat } from '../../api/types'
import { textLimits, type LimitKind } from '../../lib/limits'
import { useSelection } from '../../store/selection'
import { AudioResultCard } from './audio-result-card'
import { CharCounter } from './char-counter'
import { FileDropZone } from './file-drop-zone'
import { GenerateButton } from './generate-button'
import { ProgressStatus } from './progress-status'
import { SynthControls } from './synth-controls'
import { TextEditor } from './text-editor'
import { useGenerate } from './use-generate'
import { LimitStates } from '../status/limit-states'
import { Button } from '../../components/ui/button'

export function ComposePanel() {
  const { t } = useTranslation()
  const { selectedVoice, style } = useSelection()
  const [text, setText] = useState('')
  const [speed, setSpeed] = useState(1)
  const [format, setFormat] = useState<AudioFormat>('mp3')
  const job = useGenerate()

  const isBlocked = !selectedVoice || !text.trim() || text.length > textLimits.hard || job.state === 'generating'
  const params = selectedVoice && { text, voiceId: selectedVoice.id, engine: selectedVoice.engine, style, speed, format }

  useEffect(() => {
    const running = job.lastParams
    if (job.state !== 'generating' || !running) return
    if (!selectedVoice || running.text !== text || running.voiceId !== selectedVoice.id || running.style !== style || running.speed !== speed || running.format !== format) {
      job.cancel()
    }
  }, [text, selectedVoice, style, speed, format, job])

  return (
    <div className="space-y-4">
      <div>
        <TextEditor value={text} onChange={setText} disabled={job.state === 'generating'} />
        <div className="mt-2">
          <FileDropZone onText={setText} disabled={job.state === 'generating'} />
        </div>
      </div>

      {!text && <p className="text-sm leading-6 text-[var(--color-muted)]">{t('compose.emptyHint')}</p>}

      <CharCounter count={text.length} />

      <SynthControls speed={speed} format={format} onSpeed={setSpeed} onFormat={setFormat} />

      <LimitStates kind={job.error as LimitKind} />

      <div className="flex flex-wrap items-center gap-3">
        <GenerateButton
          disabled={isBlocked}
          state={job.state}
          onClick={() => {
            if (params) void job.generate(params)
          }}
        />
        {job.state === 'generating' && <Button variant="secondary" onClick={job.cancel}>{t('action.cancel')}</Button>}
        {job.state === 'error' && <Button variant="secondary" onClick={job.retry}>{t('action.retry')}</Button>}
        {job.state === 'error' && (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            {t('compose.error')}
          </p>
        )}
      </div>

      <ProgressStatus state={job.state} progress={job.progress} />

      {job.result && (
        <AudioResultCard
          result={job.result}
          params={job.lastParams ?? params!}
          onRegenerate={() => {
            if (params) void job.generate(params)
          }}
        />
      )}
    </div>
  )
}
