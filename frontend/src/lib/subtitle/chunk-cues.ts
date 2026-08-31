import type { TranscriptSegment, TranscriptWord } from '../../api/transcribe-api'
import { defaultSubtitleOptions, subtitleConventions, type SubtitleOptions } from './conventions'

export type SubtitleCue = { start: number; end: number; lines: string[] }
const cjk = /[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]/u
const punctuation = /[.!?。！？]$/u

function joinWords(words: TranscriptWord[]) { return words.map(word => word.text).join(' ').replace(/\s+([,.!?;:])/gu, '$1') }
function characterLength(value: string) { return Array.from(value.replace(/\s/gu, '')).length }
function maxCps(text: string) { return cjk.test(text) ? subtitleConventions.maxCjkCps : subtitleConventions.maxLatinCps }
function duration(start: number, end: number, text: string) {
  const readingTime = characterLength(text) / maxCps(text)
  return Math.min(subtitleConventions.maxCueSeconds, Math.max(subtitleConventions.minCueSeconds, end - start, readingTime))
}

function fallbackTokens(value: string) {
  const text = value.trim()
  if (!text) return []
  const whitespaceTokens = text.split(/\s+/u).filter(Boolean)
  if (whitespaceTokens.length > 1 || !cjk.test(text)) return whitespaceTokens
  if (typeof Intl.Segmenter !== 'function') return Array.from(text)

  const tokens: string[] = []
  for (const part of new Intl.Segmenter(undefined, { granularity: 'word' }).segment(text)) {
    if (part.isWordLike || !tokens.length) tokens.push(part.segment)
    else tokens[tokens.length - 1] += part.segment
  }
  return tokens
}

function timedWords(segment: TranscriptSegment): TranscriptWord[] {
  if (segment.words.length) return segment.words
  const tokens = fallbackTokens(segment.text)
  const step = (segment.end - segment.start) / Math.max(tokens.length, 1)
  return tokens.map((text, index) => ({
    text,
    start: segment.start + index * step,
    end: segment.start + (index + 1) * step,
  }))
}

function linesFor(words: TranscriptWord[], maxChars: number, maxLines: number) {
  const lines: string[] = ['']
  for (const word of words) {
    const line = lines[lines.length - 1]
    const separator = line ? ' ' : ''
    if (line && (line + separator + word.text).length > maxChars && lines.length < maxLines) lines.push(word.text)
    else lines[lines.length - 1] += separator + word.text
  }
  return lines
}

function mustSplit(words: TranscriptWord[], candidate: TranscriptWord, options: SubtitleOptions) {
  const prospective = [...words, candidate]
  const text = joinWords(prospective)
  const cueDuration = candidate.end - prospective[0].start
  const lineOverflow = linesFor(prospective, options.maxCharsPerLine, options.maxLinesPerCue).some(line => line.length > options.maxCharsPerLine)
  return lineOverflow || cueDuration > subtitleConventions.maxCueSeconds || characterLength(text) / Math.max(cueDuration, 0.01) > maxCps(text)
}

function makeCue(words: TranscriptWord[], options: SubtitleOptions): SubtitleCue {
  const start = words[0].start
  const rawEnd = words[words.length - 1].end
  const text = joinWords(words)
  return { start, end: start + duration(start, rawEnd, text), lines: linesFor(words, options.maxCharsPerLine, options.maxLinesPerCue) }
}

export function chunkCues(segments: TranscriptSegment[], input: Partial<SubtitleOptions> = {}): SubtitleCue[] {
  const options = { ...defaultSubtitleOptions, ...input }
  const words = segments.flatMap(timedWords)
  if (options.granularity === 'word') {
    return words.map(word => ({ start: word.start, end: word.end, lines: [word.text] }))
  }
  const cues: SubtitleCue[] = []
  let buffer: TranscriptWord[] = []
  for (const word of words) {
    if (buffer.length && mustSplit(buffer, word, options)) { cues.push(makeCue(buffer, options)); buffer = [] }
    buffer.push(word)
    if (punctuation.test(word.text) && buffer.length > 1) { cues.push(makeCue(buffer, options)); buffer = [] }
  }
  if (buffer.length) cues.push(makeCue(buffer, options))
  return cues
}
