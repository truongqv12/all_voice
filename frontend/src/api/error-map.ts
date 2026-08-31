import { ApiError } from './http-client';
import type { LimitKind } from '../lib/limits';

export function mapErrorToLimitKind(err: unknown): LimitKind | null {
  if (err instanceof ApiError) {
    switch (err.code) {
      case 'rate_limit_exceeded': return 'rate';
      case 'quota_exceeded': return 'quota';
      case 'input_too_long': return 'too-long';
      case 'server_overloaded': return 'overloaded';
      case 'invalid_audio_file': return 'audio-invalid';
      case 'audio_file_too_large': return 'audio-too-large';
      case 'preview_not_found': return 'no-preview';
      case 'invalid_api_key': return 'auth';
      case 'asr_unavailable': return 'asr-unavailable';
      case 'timeout': return 'timeout';
    }
    if (err.status === 413) return 'asr-too-long';
    if (err.status === 429) return 'rate';
    if (err.status === 402) return 'quota';
    if (err.status === 503) return 'overloaded';
  }
  return null;
}
