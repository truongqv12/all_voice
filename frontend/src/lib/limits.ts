export const textLimits = { soft: 1200, hard: 20000 } as const

export type LimitKind = 'rate' | 'quota' | 'too-long' | 'overloaded' | 'asr-too-long';
