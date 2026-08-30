import { apiFetch, apiJson, apiBlob } from './http-client';
import type { TtsApi } from './tts-api';
import type { Voice, SynthParams, SynthResult } from './types';

interface VoiceItem {
  id: string;
  name: string;
  model: 'vieneu' | 'kokoro' | 'voicevox' | 'clone';
  language: string;
  styles?: string[];
  preview_url?: string;
}

const voiceCache = new Map<string, { engine: 'vieneu' | 'kokoro' | 'voicevox' | 'clone'; styles: string[]; previewUrl?: string }>();

const BASE_URL = import.meta.env.VITE_API_BASE || '/v1';

export const httpTtsApi: TtsApi = {
  async listVoices(): Promise<Voice[]> {
    const data = await apiJson<VoiceItem[]>('/voices');
    const voices: Voice[] = data.map(item => {
      const previewUrl = item.preview_url;
      const engine = item.model;
      
      voiceCache.set(item.id, { engine, styles: item.styles || [], previewUrl });
      
      return {
        id: item.id,
        name: item.name,
        language: item.language as any,
        engine,
        gender: 'neutral',
        styles: item.styles || [],
        description: `${item.language.toUpperCase()} · ${engine}`,
        previewUrl,
      };
    });
    return voices;
  },

  async getPreviewUrl(voice: Voice): Promise<string> {
    if (voice.previewUrl) return voice.previewUrl;
    return `${BASE_URL}/voices/${voice.engine}/${voice.id}/preview`;
  },

  async synth(params: SynthParams): Promise<SynthResult> {
    if (voiceCache.size === 0) await this.listVoices();
    const cached = voiceCache.get(params.voiceId);
    const model = cached?.engine || 'vieneu';
    
    const payload: any = {
      model,
      input: params.text,
      voice: params.voiceId,
      response_format: params.format,
      speed: params.speed,
    };
    if (cached && cached.styles.includes(params.style)) {
      payload.style = params.style;
    }

    const blob = await apiBlob('/audio/speech', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return {
      audioUrl: URL.createObjectURL(blob),
      filename: `all-voice-${params.voiceId}.${params.format}`,
      previewOnly: false,
    };
  },

  async synthStream(params: SynthParams, onProgress: (percent: number) => void): Promise<SynthResult> {
    if (voiceCache.size === 0) await this.listVoices();
    const cached = voiceCache.get(params.voiceId);
    const model = cached?.engine || 'vieneu';
    
    const payload: any = {
      model,
      input: params.text,
      voice: params.voiceId,
      response_format: 'mp3',
    };
    if (cached && cached.styles.includes(params.style)) {
      payload.style = params.style;
    }

    const res = await apiFetch('/audio/stream', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    
    if (!res.body) throw new Error('No body in response');
    const reader = res.body.getReader();
    const chunks: Uint8Array[] = [];
    let received = 0;
    onProgress(0); // indeterminate marker
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.length;
      onProgress(received); 
    }
    const blob = new Blob(chunks as any[], { type: 'audio/mpeg' });
    return {
      audioUrl: URL.createObjectURL(blob),
      filename: `all-voice-${params.voiceId}.mp3`,
      previewOnly: false,
    };
  },
};
