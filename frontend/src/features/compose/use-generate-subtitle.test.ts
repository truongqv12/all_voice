import { describe, expect, it } from 'vitest'
import { defaultSubtitleOptions } from '../../lib/subtitle/conventions'
import { nativeCuesToSubtitleCues } from './use-generate-subtitle'

describe('nativeCuesToSubtitleCues', () => {
  it('keeps one SRT cue per VOICEVOX accent phrase and wraps long text', () => {
    const cues = nativeCuesToSubtitleCues([
      { start: 0.1, end: 1.2, text: 'こんにちは世界' },
      { start: 1.2, end: 2.1, text: 'です' },
    ], { ...defaultSubtitleOptions, maxCharsPerLine: 4, maxLinesPerCue: 2 })

    expect(cues).toEqual([
      { start: 0.1, end: 1.2, lines: ['こんにち', 'は世界'] },
      { start: 1.2, end: 2.1, lines: ['です'] },
    ])
  })

  it('splits an oversized accent phrase without dropping characters', () => {
    const cues = nativeCuesToSubtitleCues(
      [{ start: 0, end: 2, text: 'あいうえおかきくけこさしすせそ' }],
      { ...defaultSubtitleOptions, maxCharsPerLine: 4, maxLinesPerCue: 2 },
    )

    expect(cues.flatMap(cue => cue.lines).join('')).toBe('あいうえおかきくけこさしすせそ')
    expect(cues).toHaveLength(2)
    expect(cues[0]).toMatchObject({ start: 0, end: 16 / 15 })
    expect(cues[1]).toMatchObject({ start: 16 / 15, end: 2 })
  })
})
