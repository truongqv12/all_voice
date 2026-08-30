import { useEffect, useRef, useState } from 'react'
import { mockTranscribeApi } from '../../api/mock-transcribe-api'
import type { TranscriptionResult } from '../../api/transcribe-api'

export type TranscribeState = 'idle' | 'uploading' | 'transcribing' | 'done' | 'error'
const supported = /\.(mp3|wav|m4a)$/iu

export function useTranscribe() {
  const [state, setState] = useState<TranscribeState>('idle')
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<TranscriptionResult | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const url = useRef<string | null>(null)

  useEffect(() => () => { if (url.current) URL.revokeObjectURL(url.current) }, [])

  async function transcribe(nextFile: File) {
    if (!supported.test(nextFile.name)) { setError('format'); setState('error'); return }
    if (nextFile.size > 50 * 1024 * 1024) { setError('size'); setState('error'); return }
    if (url.current) URL.revokeObjectURL(url.current)
    url.current = URL.createObjectURL(nextFile)
    setFile(nextFile); setResult(null); setError(''); setState('uploading'); setProgress(0)
    try {
      const transcription = await mockTranscribeApi.transcribe(nextFile, (stage, percent) => { setState(stage); setProgress(percent) })
      setResult(transcription); setState('done')
    } catch {
      setError('generic'); setState('error')
    }
  }

  return { state, progress, result, file, audioUrl: url.current, error, transcribe }
}
