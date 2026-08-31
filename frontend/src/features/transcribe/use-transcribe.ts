import { useEffect, useRef, useState } from 'react'
import { isAbortError } from '../../api/http-client'
import { useTranscribeApi } from '../../api/api-context'
import type { TranscriptionResult } from '../../api/transcribe-api'
import { mapErrorToLimitKind } from '../../api/error-map'
import type { LimitKind } from '../../lib/limits'

export type TranscribeState = 'idle' | 'uploading' | 'transcribing' | 'done' | 'error'
const supported = /\.(mp3|wav|m4a)$/iu

export function useTranscribe() {
  const api = useTranscribeApi()
  const requestId = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const lastFile = useRef<File | null>(null)
  const running = useRef(false)
  const url = useRef<string | null>(null)
  const [state, setState] = useState<TranscribeState>('idle')
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<TranscriptionResult | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | LimitKind>('')

  function replaceUrl(nextFile: File) {
    if (url.current) URL.revokeObjectURL(url.current)
    url.current = URL.createObjectURL(nextFile)
  }

  async function transcribe(nextFile: File) {
    if (running.current) return
    if (!supported.test(nextFile.name)) { setError('format'); setState('error'); return }
    if (nextFile.size > 25 * 1024 * 1024) { setError('size'); setState('error'); return }
    const id = ++requestId.current
    const aborter = new AbortController()
    controller.current = aborter
    running.current = true
    lastFile.current = nextFile
    replaceUrl(nextFile)
    setFile(nextFile)
    setResult(null)
    setError('')
    setState('uploading')
    setProgress(0)
    try {
      const transcription = await api.transcribe(nextFile, (stage, percent) => {
        if (id === requestId.current) {
          setState(stage)
          setProgress(percent)
        }
      }, { signal: aborter.signal })
      if (id !== requestId.current) return
      setResult(transcription)
      setState('done')
    } catch (cause) {
      if (id !== requestId.current) return
      if (isAbortError(cause)) {
        setState('idle')
        setProgress(0)
        return
      }
      setError(mapErrorToLimitKind(cause) || 'generic')
      setState('error')
    } finally {
      if (id === requestId.current) {
        running.current = false
        controller.current = null
      }
    }
  }

  function cancel() {
    if (!running.current) return
    requestId.current += 1
    running.current = false
    controller.current?.abort()
    controller.current = null
    setState('idle')
    setProgress(0)
  }

  function retry() {
    if (lastFile.current) void transcribe(lastFile.current)
  }

  useEffect(() => () => {
    requestId.current += 1
    controller.current?.abort()
    if (url.current) URL.revokeObjectURL(url.current)
  }, [])

  return { state, progress, result, file, audioUrl: url.current, error, transcribe, cancel, retry }
}
