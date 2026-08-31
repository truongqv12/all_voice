import { useEffect, useRef, useState } from 'react'
import { useTranscribeApi } from '../../api/api-context'
import type { TranscriptionResult } from '../../api/transcribe-api'
import { mapErrorToLimitKind } from '../../api/error-map'
import type { LimitKind } from '../../lib/limits'
import { transcriptFixture } from '../../data/transcript-fixture'

export type TranscribeState = 'idle' | 'uploading' | 'transcribing' | 'done' | 'error'
const supported = /\.(mp3|wav|m4a)$/iu

const wait = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

export function useTranscribe() {
  const api = useTranscribeApi()
  const [state, setState] = useState<TranscribeState>('idle')
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<TranscriptionResult | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | LimitKind>('')
  const url = useRef<string | null>(null)

  useEffect(() => () => { if (url.current) URL.revokeObjectURL(url.current) }, [])

  async function transcribe(nextFile: File) {
    if (!supported.test(nextFile.name)) { setError('format'); setState('error'); return }
    if (nextFile.size > 25 * 1024 * 1024) { setError('size'); setState('error'); return }
    if (url.current) URL.revokeObjectURL(url.current)
    url.current = URL.createObjectURL(nextFile)
    setFile(nextFile); setResult(null); setError(''); setState('uploading'); setProgress(0)
    try {
      const transcription = await api.transcribe(nextFile, (stage, percent) => { setState(stage); setProgress(percent) })
      setResult(transcription); setState('done')
    } catch (err) {
      setError(mapErrorToLimitKind(err) || 'generic'); setState('error')
    }
  }

  async function transcribeSample() {
    if (url.current) URL.revokeObjectURL(url.current)
    url.current = null
    const fakeFile = new File([''], 'sample-vietnamese-podcast.mp3', { type: 'audio/mpeg' })
    setFile(fakeFile); setResult(null); setError(''); setState('uploading'); setProgress(0)
    
    // Simulate progress for the mock sample
    for (const percent of [20, 48, 100]) { await wait(260); setState('uploading'); setProgress(percent) }
    for (const percent of [18, 56, 100]) { await wait(330); setState('transcribing'); setProgress(percent) }
    setResult(transcriptFixture); setState('done')
  }

  return { state, progress, result, file, audioUrl: url.current, error, transcribe, transcribeSample }
}
