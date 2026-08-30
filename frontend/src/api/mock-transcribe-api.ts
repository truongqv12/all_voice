import { transcriptFixture } from '../data/transcript-fixture'
import type { TranscribeApi } from './transcribe-api'

const wait = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

export const mockTranscribeApi: TranscribeApi = {
  async transcribe(_file, onProgress) {
    for (const percent of [20, 48, 100]) { await wait(260); onProgress('uploading', percent) }
    for (const percent of [18, 56, 100]) { await wait(330); onProgress('transcribing', percent) }
    return transcriptFixture
  },
}
