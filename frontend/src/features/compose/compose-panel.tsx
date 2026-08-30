import { useState } from 'react'
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

export function ComposePanel() {
  const { t } = useTranslation()
  const { selectedVoice, style } = useSelection()
  const [text, setText] = useState('')
  const [speed, setSpeed] = useState(1)
  const [format, setFormat] = useState<AudioFormat>('mp3')
  const job = useGenerate()

  const isBlocked = !selectedVoice || !text.trim() || text.length > textLimits.hard || job.state === 'generating'
  const params = selectedVoice && { text, voiceId: selectedVoice.id, style, speed, format }

  return (
    <div className="space-y-4">
      <div>
        <TextEditor value={text} onChange={setText} />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-[var(--color-muted)]">{t('compose.quickFill')}</span>
          <button
            type="button"
            onClick={() => setText(t('compose.sampleShort'))}
            className="cursor-pointer rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-xs font-medium text-[var(--color-text)] transition-colors hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]"
          >
            Chào mừng ngắn
          </button>
          <button
            type="button"
            onClick={() => setText(t('compose.sampleDialogue'))}
            className="cursor-pointer rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-xs font-medium text-[var(--color-text)] transition-colors hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]"
          >
            Thời tiết / Hội thoại
          </button>
          <button
            type="button"
            onClick={() => setText(t('compose.sampleStream'))}
            className="cursor-pointer rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-xs font-medium text-[var(--color-text)] transition-colors hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]"
          >
            Đoạn văn dài
          </button>
        </div>
        <div className="mt-2">
          <FileDropZone onText={setText} />
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
          onRegenerate={() => {
            if (params) void job.generate(params)
          }}
        />
      )}
    </div>
  )
}
