import { ApiError } from './http-client';
import type { LimitKind } from '../lib/limits';

export function mapErrorToLimitKind(err: unknown): LimitKind | null {
  if (err instanceof ApiError) {
    if (err.status === 413) return 'asr-too-long';
    if (err.status === 429) return 'rate';
    if (err.status === 402) return 'quota';
    if (err.status === 503) return 'overloaded';

    switch (err.code) {
      case 'rate_limit_exceeded': return 'rate';
      case 'quota_exceeded': return 'quota';
      case 'input_too_long': return 'too-long';
      case 'server_overloaded': return 'overloaded';
    }
  }
  return null;
}
