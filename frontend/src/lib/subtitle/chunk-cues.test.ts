import { describe, expect, it } from 'vitest'
import type { TranscriptSegment } from '../../api/transcribe-api'
import { chunkCues } from './chunk-cues'
import { subtitleConventions } from './conventions'
import { toSrt } from './to-srt'
import { toVtt } from './to-vtt'
import { utf8TextBlob } from '../download'

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

  it('creates one cue per timestamped word in word mode', () => {
    const cues = chunkCues([segment(['Xin', 'chào', 'bạn.'], 0.4)], { granularity: 'word' })

    expect(cues.map(cue => cue.lines)).toEqual([['Xin'], ['chào'], ['bạn.']])
    expect(cues.map(cue => cue.start)).toEqual([0, 0.4, 0.8])
    expect(cues[0].end).toBeCloseTo(0.38)
    expect(cues[1].end).toBeCloseTo(0.78)
    expect(cues[2].end).toBeCloseTo(1.18)
  })

  it('groups words into readable cues in line mode', () => {
    const cues = chunkCues([segment(['Xin', 'chào', 'bạn.'], 0.4)], { granularity: 'line' })

    expect(cues).toHaveLength(1)
    expect(cues[0].lines).toEqual(['Xin chào bạn.'])
  })

  it('writes UTF-8 text downloads with a BOM and preserves Vietnamese', async () => {
    const blob = utf8TextBlob('Tiếng Việt', 'application/x-subrip')
    const bytes = new Uint8Array(await blob.arrayBuffer())

    expect(Array.from(bytes.slice(0, 3))).toEqual([0xef, 0xbb, 0xbf])
    expect(new TextDecoder().decode(bytes.slice(3))).toBe('Tiếng Việt')
    expect(blob.type).toBe('application/x-subrip;charset=utf-8')
  })

  it('falls back to segment timing when word timestamps are unavailable', () => {
    const source: TranscriptSegment = {
      id: 'fallback',
      text: 'Xin chào',
      start: 1,
      end: 3,
      words: [],
    }

    expect(chunkCues([source], { granularity: 'word' })).toEqual([
      { start: 1, end: 2, lines: ['Xin'] },
      { start: 2, end: 3, lines: ['chào'] },
    ])
    expect(chunkCues([source], { granularity: 'line' })[0].lines).toEqual(['Xin chào'])
  })

  it('segments CJK fallback text without empty or overflowing lines', () => {
    const source: TranscriptSegment = {
      id: 'fallback-ja',
      text: '今日は良い天気です。',
      start: 0,
      end: 5,
      words: [],
    }
    const wordCues = chunkCues([source], { granularity: 'word' })
    const lineCues = chunkCues([source], {
      granularity: 'line',
      maxCharsPerLine: 4,
      maxLinesPerCue: 2,
    })

    expect(wordCues.map(cue => cue.lines[0])).toEqual(['今日', 'は', '良い', '天気', 'です。'])
    expect(lineCues.flatMap(cue => cue.lines).every(line => line.length > 0 && line.length <= 4)).toBe(true)
  })
})
