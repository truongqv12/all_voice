export type TranscriptWord = {
  text: string
  start: number
  end: number
}

export type TranscriptSegment = {
  id: string
  text: string
  start: number
  end: number
  words: TranscriptWord[]
}

export type TranscriptionResult = {
  language: string
  segments: TranscriptSegment[]
}

export type TranscribeProgress = 'uploading' | 'transcribing'
export type TranscribeOptions = { prompt?: string; signal?: AbortSignal; timeoutMs?: number }

export interface TranscribeApi {
  transcribe(file: File, onProgress: (stage: TranscribeProgress, percent: number) => void, options?: TranscribeOptions): Promise<TranscriptionResult>
}
