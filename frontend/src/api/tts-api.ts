import type { SynthParams, SynthResult, Voice } from './types'
import type { HttpClientOptions } from './http-client'

export type SpeechTimingCue = { start: number; end: number; text: string }

export interface TtsApi {
  listVoices(): Promise<Voice[]>
  getPreviewUrl(voice: Voice): Promise<string>
  synth(params: SynthParams, options?: HttpClientOptions): Promise<SynthResult>
  synthStream(params: SynthParams, onProgress: (percent: number) => void, options?: HttpClientOptions): Promise<SynthResult>
  getSpeechTiming(params: SynthParams, options?: HttpClientOptions): Promise<SpeechTimingCue[]>
}
