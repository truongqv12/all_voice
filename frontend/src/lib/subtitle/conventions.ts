export const subtitleConventions = {
  maxCharsPerLine: 42,
  maxLinesPerCue: 2,
  minCueSeconds: 0.83,
  maxCueSeconds: 7,
  maxLatinCps: 20,
  maxCjkCps: 4,
} as const

export type SubtitleOptions = {
  maxCharsPerLine: number
  maxLinesPerCue: number
  granularity: 'word' | 'sentence'
}

export const defaultSubtitleOptions: SubtitleOptions = {
  maxCharsPerLine: subtitleConventions.maxCharsPerLine,
  maxLinesPerCue: subtitleConventions.maxLinesPerCue,
  granularity: 'word',
}
