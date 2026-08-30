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

export interface TranscribeApi {
  transcribe(file: File, onProgress: (stage: TranscribeProgress, percent: number) => void): Promise<TranscriptionResult>
}
