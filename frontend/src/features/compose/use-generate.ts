import { useEffect, useRef, useState } from 'react'
import { isAbortError } from '../../api/http-client'
import { mapErrorToLimitKind } from '../../api/error-map'
import { useTtsApi } from '../../api/api-context'
import type { SynthParams, SynthResult } from '../../api/types'
import type { LimitKind } from '../../lib/limits'

export type GenerateState = 'idle' | 'generating' | 'success' | 'error'

export function useGenerate() {
  const api = useTtsApi()
  const requestId = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const lastParams = useRef<SynthParams | null>(null)
  const running = useRef(false)
  const [state, setState] = useState<GenerateState>('idle')
  const [progress, setProgress] = useState<number | null>(null)
  const [result, setResult] = useState<SynthResult | null>(null)
  const [error, setError] = useState<string | LimitKind>('')

  function discard(next: SynthResult | null) {
    if (next?.audioUrl.startsWith('blob:')) URL.revokeObjectURL(next.audioUrl)
  }

  async function generate(params: SynthParams) {
    if (running.current) return
    const id = ++requestId.current
    const aborter = new AbortController()
    controller.current = aborter
    lastParams.current = params
    running.current = true
    setState('generating')
    setResult(current => {
      discard(current)
      return null
    })
    setError('')
    const streams = params.text.length > 2000
    setProgress(streams ? 0 : null)
    try {
      const next = streams
        ? await api.synthStream(params, setProgress, { signal: aborter.signal })
        : await api.synth(params, { signal: aborter.signal })
      if (id !== requestId.current) {
        discard(next)
        return
      }
      setResult(next)
      setState('success')
    } catch (cause) {
      if (id !== requestId.current) return
      if (isAbortError(cause)) {
        setState('idle')
        setProgress(null)
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
    setProgress(null)
  }

  function retry() {
    if (lastParams.current) void generate(lastParams.current)
  }

  function reset() {
    cancel()
    setResult(current => {
      discard(current)
      return null
    })
    setError('')
  }

  useEffect(() => () => {
    requestId.current += 1
    controller.current?.abort()
  }, [])

  return { state, progress, result, lastParams: lastParams.current, error, generate, cancel, retry, reset }
}
