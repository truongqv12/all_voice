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

function linesFor(words: TranscriptWord[], maxChars: number, maxLines: number) {
  const lines: string[] = ['']
  for (const word of words) {
    const line = lines[lines.length - 1]
    const separator = line ? ' ' : ''
    if ((line + separator + word.text).length > maxChars && lines.length < maxLines) lines.push(word.text)
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
  if (options.granularity === 'sentence') return segments.flatMap(segment => {
    const words = segment.words
    return words.length ? chunkCues([{ ...segment, words }], { ...options, granularity: 'word' }) : []
  })
  const cues: SubtitleCue[] = []
  let buffer: TranscriptWord[] = []
  for (const word of segments.flatMap(segment => segment.words)) {
    if (buffer.length && mustSplit(buffer, word, options)) { cues.push(makeCue(buffer, options)); buffer = [] }
    buffer.push(word)
    if (punctuation.test(word.text) && buffer.length > 1) { cues.push(makeCue(buffer, options)); buffer = [] }
  }
  if (buffer.length) cues.push(makeCue(buffer, options))
  return cues
}
