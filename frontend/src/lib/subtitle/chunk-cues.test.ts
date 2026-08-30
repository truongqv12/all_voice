import { describe, expect, it } from 'vitest'
import type { TranscriptSegment } from '../../api/transcribe-api'
import { chunkCues } from './chunk-cues'
import { subtitleConventions } from './conventions'
import { toSrt } from './to-srt'
import { toVtt } from './to-vtt'

function segment(words: string[], step = 0.3): TranscriptSegment {
  return { id: 'sample', text: words.join(' '), start: 0, end: words.length * step, words: words.map((text, index) => ({ text, start: index * step, end: index * step + step - 0.02 })) }
}

describe('chunkCues', () => {
  it('wraps a long sentence within configured line and cue limits', () => {
    const cues = chunkCues([segment('This is a deliberately long subtitle sentence that should wrap into readable caption lines before becoming difficult to scan.'.split(' '))], { maxCharsPerLine: 24, maxLinesPerCue: 2 })
    expect(cues).not.toHaveLength(0)
    expect(cues.every(cue => cue.lines.length <= 2 && cue.lines.every(line => line.length <= 24))).toBe(true)
  })

  it('breaks at punctuation and keeps cue durations bounded', () => {
    const cues = chunkCues([segment(['Hello,', 'world.', 'Next', 'sentence', 'here.'], 0.5)])
    expect(cues).toHaveLength(2)
    expect(cues.every(cue => cue.end - cue.start >= subtitleConventions.minCueSeconds && cue.end - cue.start <= subtitleConventions.maxCueSeconds)).toBe(true)
  })

  it('uses the CJK reading-rate limit', () => {
    const cues = chunkCues([segment(['你好', '世界，', '这是', '字幕。'], 0.15)])
    expect(cues.every(cue => cue.lines.join('').replace(/\s/gu, '').length / (cue.end - cue.start) <= subtitleConventions.maxCjkCps)).toBe(true)
  })

  it('serializes valid SRT and VTT timestamps', () => {
    const cues = chunkCues([segment(['Hello', 'world.'])])
    expect(toSrt(cues)).toMatch(/^1\n00:00:00,000 --> 00:00:00,830/mu)
    expect(toVtt(cues)).toMatch(/^WEBVTT\n\n00:00:00\.000 --> 00:00:00\.830/mu)
  })
})
