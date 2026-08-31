import { useEffect, useRef, useState } from 'react'
import { isAbortError } from '../../api/http-client'
import { mapErrorToLimitKind } from '../../api/error-map'
import { useTranscribeApi, useTtsApi } from '../../api/api-context'
import type { SynthParams, SynthResult } from '../../api/types'
import type { LimitKind } from '../../lib/limits'
import type { SubtitleCue } from '../../lib/subtitle/chunk-cues'
import { chunkCues } from '../../lib/subtitle/chunk-cues'
import type { SubtitleOptions } from '../../lib/subtitle/conventions'
import { toSrt } from '../../lib/subtitle/to-srt'

export type SubtitleState = 'idle' | 'generating' | 'success' | 'error'
type SubtitleRequest = { result: SynthResult; params: SynthParams; options: SubtitleOptions }

export function nativeCuesToSubtitleCues(cues: { start: number; end: number; text: string }[], options: SubtitleOptions): SubtitleCue[] {
  const charsPerCue = Math.max(1, options.maxCharsPerLine * Math.max(1, options.maxLinesPerCue))
  return cues.flatMap(cue => {
    const characters = Array.from(cue.text)
    const duration = cue.end - cue.start
    return Array.from({ length: Math.ceil(characters.length / charsPerCue) }, (_, index) => {
      const startIndex = index * charsPerCue
      const section = characters.slice(startIndex, startIndex + charsPerCue)
      const endIndex = startIndex + section.length
      const lines = Array.from({ length: Math.ceil(section.length / options.maxCharsPerLine) }, (_, line) => section.slice(line * options.maxCharsPerLine, (line + 1) * options.maxCharsPerLine).join(''))
      return {
        start: cue.start + duration * startIndex / characters.length,
        end: cue.start + duration * endIndex / characters.length,
        lines,
      }
    })
  })
}

function download(content: string, filename: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'application/x-subrip;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename.replace(/\.[^.]+$/u, '')}.srt`
  link.click()
  URL.revokeObjectURL(url)
}

export function useGenerateSubtitle() {
  const transcribe = useTranscribeApi()
  const tts = useTtsApi()
  const requestId = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const lastRequest = useRef<SubtitleRequest | null>(null)
  const [state, setState] = useState<SubtitleState>('idle')
  const [error, setError] = useState<LimitKind | 'generic' | ''>('')
  const [native, setNative] = useState(false)

  async function generate(request: SubtitleRequest) {
    const id = ++requestId.current
    const aborter = new AbortController()
    controller.current?.abort()
    controller.current = aborter
    lastRequest.current = request
    setState('generating')
    setError('')
    setNative(request.result.engine === 'voicevox')
    try {
      const cues = request.result.engine === 'voicevox'
        ? nativeCuesToSubtitleCues(await tts.getSpeechTiming(request.params, { signal: aborter.signal }), request.options)
        : chunkCues((await transcribe.transcribe(
          new File([request.result.audioBlob], request.result.filename, { type: request.result.audioBlob.type || 'audio/mpeg' }),
          () => undefined,
          { prompt: request.params.text, signal: aborter.signal },
        )).segments, request.options)
      if (id !== requestId.current) return
      download(toSrt(cues), request.result.filename)
      setState('success')
    } catch (cause) {
      if (id !== requestId.current) return
      if (isAbortError(cause)) {
        setState('idle')
        return
      }
      setError(mapErrorToLimitKind(cause) || 'generic')
      setState('error')
    } finally {
      if (id === requestId.current) controller.current = null
    }
  }

  function cancel() {
    requestId.current += 1
    controller.current?.abort()
    controller.current = null
    setState('idle')
  }

  function retry() {
    if (lastRequest.current) void generate(lastRequest.current)
  }

  useEffect(() => () => {
    requestId.current += 1
    controller.current?.abort()
    controller.current = null
  }, [])

  return { state, error, native, generate, cancel, retry }
}
