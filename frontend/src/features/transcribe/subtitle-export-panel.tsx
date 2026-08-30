import { Clipboard, Download, FileText, SplitSquareVertical } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TranscriptionResult } from '../../api/transcribe-api'
import { Button } from '../../components/ui/button'
import { Select, type SelectOption } from '../../components/ui/select'
import { chunkCues } from '../../lib/subtitle/chunk-cues'
import { defaultSubtitleOptions, type SubtitleOptions } from '../../lib/subtitle/conventions'
import { toSrt } from '../../lib/subtitle/to-srt'
import { toTxt } from '../../lib/subtitle/to-txt'
import { toVtt } from '../../lib/subtitle/to-vtt'
import { SubtitlePreview } from './subtitle-preview'

type ExportFormat = 'srt' | 'vtt' | 'txt'
function content(format: ExportFormat, result: TranscriptionResult, options: SubtitleOptions) {
  const cues = chunkCues(result.segments, options)
  return { cues, text: format === 'srt' ? toSrt(cues) : format === 'vtt' ? toVtt(cues) : toTxt(cues) }
}
function safeName(name: string) {
  return name.replace(/\.[^.]+$/u, '').replace(/[^\w-]+/gu, '-').replace(/^-|-$/gu, '') || 'transcript'
}

export function SubtitleExportPanel({ result, filename }: { result: TranscriptionResult; filename: string }) {
  const { t } = useTranslation()
  const [format, setFormat] = useState<ExportFormat>('srt')
  const [options, setOptions] = useState(defaultSubtitleOptions)
  const [copied, setCopied] = useState(false)
  const exportData = useMemo(() => content(format, result, options), [format, options, result])

  function update<K extends keyof SubtitleOptions>(key: K, value: SubtitleOptions[K]) {
    setOptions(current => ({ ...current, [key]: value }))
  }
  function download() {
    const blob = new Blob([exportData.text], { type: format === 'txt' ? 'text/plain' : 'text/vtt' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${safeName(filename)}.${format}`
    link.click()
    URL.revokeObjectURL(url)
  }
  async function copy() {
    await navigator.clipboard.writeText(exportData.text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  const formatOptions: SelectOption[] = [
    { value: 'srt', label: 'SRT', description: 'SubRip (YouTube, Premiere, VLC)', icon: <FileText size={15} className="shrink-0 text-[var(--color-primary)]" /> },
    { value: 'vtt', label: 'VTT', description: 'WebVTT (HTML5 Video)', icon: <FileText size={15} className="shrink-0 text-[var(--color-primary)]" /> },
    { value: 'txt', label: 'TXT', description: 'Văn bản thuần theo dòng', icon: <FileText size={15} className="shrink-0 text-[var(--color-primary)]" /> },
  ]

  const granularityOptions: SelectOption[] = [
    { value: 'word', label: t('transcribe.wordAccurate'), description: 'Khớp nhịp từ', icon: <SplitSquareVertical size={15} className="shrink-0 text-[var(--color-primary)]" /> },
    { value: 'sentence', label: t('transcribe.sentence'), description: 'Theo câu trọn vẹn', icon: <SplitSquareVertical size={15} className="shrink-0 text-[var(--color-primary)]" /> },
  ]

  return (
    <section className="rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-6">
      <div>
        <p className="text-xs font-bold tracking-[0.08em] text-[var(--color-primary)]">{t('transcribe.exportEyebrow')}</p>
        <h2 className="mt-1 text-xl font-bold">{t('transcribe.exportTitle')}</h2>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div>
          <span className="block text-sm font-semibold mb-1.5">{t('transcribe.format')}</span>
          <Select
            value={format}
            options={formatOptions}
            onChange={val => setFormat(val as ExportFormat)}
            aria-label={t('transcribe.format')}
          />
        </div>

        <div>
          <span className="block text-sm font-semibold mb-1.5">{t('transcribe.granularity')}</span>
          <Select
            value={options.granularity}
            options={granularityOptions}
            onChange={val => update('granularity', val as SubtitleOptions['granularity'])}
            aria-label={t('transcribe.granularity')}
          />
        </div>

        <label className="grid gap-1.5 text-sm font-semibold">
          {t('transcribe.charsPerLine')}
          <input
            className="min-h-11 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 text-base font-normal focus-visible:border-[var(--color-primary)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid md:text-sm"
            type="number"
            min="20"
            max="60"
            value={options.maxCharsPerLine}
            onChange={event => update('maxCharsPerLine', Number(event.target.value))}
          />
        </label>

        <label className="grid gap-1.5 text-sm font-semibold">
          {t('transcribe.linesPerCue')}
          <input
            className="min-h-11 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 text-base font-normal focus-visible:border-[var(--color-primary)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid md:text-sm"
            type="number"
            min="1"
            max="2"
            value={options.maxLinesPerCue}
            onChange={event => update('maxLinesPerCue', Number(event.target.value))}
          />
        </label>
      </div>

      <SubtitlePreview cues={exportData.cues} />

      <div className="mt-4 flex flex-wrap gap-2.5">
        <Button onClick={download}>
          <Download className="shrink-0" size={17} />
          <span>{t('transcribe.download')}</span>
        </Button>
        <Button variant="secondary" onClick={() => void copy()}>
          <Clipboard className="shrink-0" size={17} />
          <span>{copied ? t('transcribe.copied') : t('transcribe.copy')}</span>
        </Button>
      </div>
    </section>
  )
}
