import type { SynthParams, SynthResult, Voice } from './types'

export interface TtsApi {
  listVoices(): Promise<Voice[]>
  getPreviewUrl(voice: Voice): Promise<string>
  synth(params: SynthParams): Promise<SynthResult>
  synthStream(params: SynthParams, onProgress: (percent: number) => void): Promise<SynthResult>
}
