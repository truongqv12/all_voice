export const textLimits = { soft: 2000, hard: 20000 } as const

export type LimitKind = 'rate' | 'quota' | 'too-long' | 'overloaded' | 'asr-too-long' | 'asr-unavailable' | 'audio-invalid' | 'audio-too-large' | 'no-preview' | 'auth' | 'timeout';
