import type { TtsApi } from './tts-api'
import type { SynthParams, SynthResult, Voice } from './types'
import { voiceFixtures } from '../data/voice-fixtures'

const sampleAudio = '/audio/mock-sample.mp3'
const delay = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

function result(params: SynthParams): SynthResult {
  return { audioUrl: sampleAudio, filename: `all-voice-${params.voiceId}.mp3`, previewOnly: true }
}

export const mockTtsApi: TtsApi = {
  async listVoices(): Promise<Voice[]> { await delay(420); return voiceFixtures },
  async getPreviewUrl(): Promise<string> { await delay(180); return sampleAudio },
  async synth(params: SynthParams): Promise<SynthResult> { await delay(900); return result(params) },
  async synthStream(params: SynthParams, onProgress: (percent: number) => void): Promise<SynthResult> {
    for (const percent of [12, 29, 51, 76, 100]) { await delay(230); onProgress(percent) }
    return result(params)
  },
}
