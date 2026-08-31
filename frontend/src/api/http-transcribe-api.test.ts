import { describe, expect, it } from 'vitest'
import { distributeWords } from './http-transcribe-api'

describe('distributeWords', () => {
  it('should assign words to strict segment boundaries', () => {
    const segments = [
      { id: 1, text: 'hello', start: 0.0, end: 1.0 },
      { id: 2, text: 'world', start: 1.0, end: 2.0 }
    ]
    const words = [
      { word: 'hello', start: 0.1, end: 0.8 },
      { word: 'world', start: 1.1, end: 1.8 }
    ]
    const result = distributeWords(segments, words)
    expect(result[0].words.length).toBe(1)
    expect(result[0].words[0].text).toBe('hello')
    expect(result[1].words.length).toBe(1)
    expect(result[1].words[0].text).toBe('world')
  })

  it('should fallback to closest segment if out of bounds', () => {
    const segments = [
      { id: 1, text: 'hello', start: 0.0, end: 1.0 },
    ]
    const words = [
      { word: 'hello', start: 1.5, end: 2.0 },
    ]
    const result = distributeWords(segments, words)
    expect(result[0].words.length).toBe(1)
    expect(result[0].words[0].text).toBe('hello')
  })

  it('should handle empty words', () => {
    const segments = [
      { id: 1, text: 'hello', start: 0.0, end: 1.0 },
    ]
    const result = distributeWords(segments, [])
    expect(result[0].words).toEqual([])
  })
})
