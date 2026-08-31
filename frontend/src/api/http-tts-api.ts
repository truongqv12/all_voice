import { ApiError, apiFetch, apiJson, apiBlob, createRequestAbort, type HttpClientOptions } from './http-client';
import type { SpeechTimingCue, TtsApi } from './tts-api';
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

const JP_STYLE_MAP: Record<string, string> = {
  'ノーマル': 'Mặc định',
  'あまあま': 'Ngọt ngào',
  'ツンツン': 'Lạnh lùng',
  'セクシー': 'Quyến rũ',
  'ささやき': 'Thì thầm',
  'ヒソヒソ': 'Nói nhỏ',
  'ヘロヘロ': 'Mệt mỏi',
  'なみだごえ': 'Giọng khóc',
  'びくびく': 'Sợ sệt',
  '怒り': 'Tức giận',
  '悲しみ': 'Buồn bã',
  '喜び': 'Vui vẻ',
  'ドッキリ': 'Bất ngờ',
  '内緒話': 'Bí mật',
  '元気': 'Tràn đầy năng lượng',
  '冷静': 'Bình tĩnh'
};

const VV_META: Record<string, { gender: 'male'|'female'|'neutral', age: string }> = {
  '四国めたん': { gender: 'female', age: 'Thiếu nữ' },
  'ずんだもん': { gender: 'female', age: 'Trẻ em' },
  '春日部つむぎ': { gender: 'female', age: 'Thiếu nữ' },
  '雨晴はう': { gender: 'female', age: 'Thanh niên' },
  '波音リツ': { gender: 'male', age: 'Trẻ em' },
  '玄野武宏': { gender: 'male', age: 'Thanh niên' },
  '白上虎太郎': { gender: 'male', age: 'Thiếu niên' },
  '青山龍星': { gender: 'male', age: 'Người lớn' },
  '冥鳴ひまり': { gender: 'female', age: 'Thiếu nữ' },
  '九州そら': { gender: 'female', age: 'Người lớn' },
  'もち子さん': { gender: 'female', age: 'Người lớn' },
  '剣崎雌雄': { gender: 'male', age: 'Người lớn' },
  'WhiteCUL': { gender: 'female', age: 'Người lớn' },
  '後鬼': { gender: 'female', age: 'Thanh niên' },
  'No.7': { gender: 'female', age: 'Thanh niên' },
  'ちび式じい': { gender: 'male', age: 'Người già' },
  '櫻歌ミコ': { gender: 'female', age: 'Trẻ em' },
  '小夜/SAYO': { gender: 'female', age: 'Trẻ em' },
  'ナースロボ＿タイプＴ': { gender: 'female', age: 'Thanh niên' },
  '†聖騎士 紅桜†': { gender: 'male', age: 'Thanh niên' },
  '雀松朱司': { gender: 'male', age: 'Thanh niên' },
  '麒ヶ島宗麟': { gender: 'male', age: 'Thanh niên' },
  '春歌ナナ': { gender: 'female', age: 'Trẻ em' },
  '猫使アル': { gender: 'female', age: 'Thiếu nữ' },
  '猫使ビィ': { gender: 'female', age: 'Trẻ em' },
  '中国うさぎ': { gender: 'female', age: 'Thiếu nữ' },
  '栗田まろん': { gender: 'male', age: 'Thiếu niên' },
  'あいえるたん': { gender: 'female', age: 'Thiếu nữ' },
  '満別花丸': { gender: 'female', age: 'Thiếu nữ' },
  '琴詠ニア': { gender: 'female', age: 'Thiếu nữ' },
};

export const httpTtsApi: TtsApi = {
  async listVoices(): Promise<Voice[]> {
    const res = await apiJson<{ data: VoiceItem[] }>('/voices');
    const voices: Voice[] = res.data.map(item => {
      const previewUrl = item.preview_url;
      const engine = item.model;
      
      let cleanName = item.name;
      if (engine === 'voicevox') {
        cleanName = cleanName.replace(/ · VOICEVOX:.*$/, '');
        for (const [jp, vn] of Object.entries(JP_STYLE_MAP)) {
          cleanName = cleanName.replace(jp, vn);
        }
      }
      
      let gender: 'male' | 'female' | 'neutral' = 'neutral';
      let age: string | undefined;
      if (cleanName.includes('Nữ')) gender = 'female';
      else if (cleanName.includes('Nam')) gender = 'male';
      else if (engine === 'voicevox') {
        gender = 'female'; // default fallback
        for (const [key, meta] of Object.entries(VV_META)) {
          if (cleanName.includes(key)) {
            gender = meta.gender;
            age = meta.age;
            break;
          }
        }
      }
      
      voiceCache.set(item.id, { engine, styles: item.styles || [], previewUrl });
      
      return {
        id: item.id,
        name: cleanName,
        language: item.language as any,
        engine,
        gender,
        age,
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

  async synth(params: SynthParams, options?: HttpClientOptions): Promise<SynthResult> {
    if (voiceCache.size === 0) await this.listVoices();
    const cached = voiceCache.get(params.voiceId);
    const model = params.engine || cached?.engine || 'vieneu';
    
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
      ...options,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return {
      audioUrl: URL.createObjectURL(blob),
      audioBlob: blob,
      filename: `all-voice-${params.voiceId}.${params.format}`,
      previewOnly: false,
      engine: model,
    };
  },

  async synthStream(params: SynthParams, onProgress: (percent: number) => void, options?: HttpClientOptions): Promise<SynthResult> {
    if (voiceCache.size === 0) await this.listVoices();
    const cached = voiceCache.get(params.voiceId);
    const model = params.engine || cached?.engine || 'vieneu';
    
    const payload: any = {
      model,
      input: params.text,
      voice: params.voiceId,
      response_format: 'mp3',
      speed: params.speed,
    };
    if (cached && cached.styles.includes(params.style)) {
      payload.style = params.style;
    }

    const abort = createRequestAbort(options);
    try {
      const res = await apiFetch('/audio/stream', {
        ...options,
        signal: abort.signal,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }, true);
      if (!res.body) throw new Error('No body in response');
      const reader = res.body.getReader();
      const chunks: Uint8Array[] = [];
      let received = 0;
      onProgress(0);
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        onProgress(received);
      }
      const blob = new Blob(chunks as unknown as BlobPart[], { type: 'audio/mpeg' });
      return {
        audioUrl: URL.createObjectURL(blob),
        audioBlob: blob,
        filename: `all-voice-${params.voiceId}.mp3`,
        previewOnly: false,
        engine: model,
      };
    } catch (error) {
      if (abort.signal.aborted) {
        throw new ApiError(0, abort.timedOut() ? 'timeout' : 'aborted', abort.timedOut() ? 'The request timed out.' : 'The request was cancelled.');
      }
      throw error;
    } finally {
      abort.dispose();
    }
  },

  async getSpeechTiming(params: SynthParams, options?: HttpClientOptions): Promise<SpeechTimingCue[]> {
    const data = await apiJson<{ cues: SpeechTimingCue[] }>('/audio/speech/timing', {
      ...options,
      method: 'POST',
      body: JSON.stringify({
        model: 'voicevox',
        input: params.text,
        voice: params.voiceId,
        speed: params.speed,
        streaming: params.text.length > 2000,
      }),
    });
    return data.cues;
  },
};
