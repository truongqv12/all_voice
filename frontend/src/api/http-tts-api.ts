import type { TtsApi } from './tts-api';

export const httpTtsApi: TtsApi = {
  async listVoices() {
    throw new Error('Not implemented');
  },
  async getPreviewUrl() {
    throw new Error('Not implemented');
  },
  async synth() {
    throw new Error('Not implemented');
  },
  async synthStream() {
    throw new Error('Not implemented');
  },
};
