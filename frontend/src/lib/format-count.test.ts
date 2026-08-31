import { describe, expect, it } from 'vitest'
import { formatCount } from './format-count'

describe('formatCount', () => {
  it('groups thousands with a dot for Vietnamese', () => {
    expect(formatCount(1234, 'vi')).toBe('1.234')
    expect(formatCount(1234567, 'vi')).toBe('1.234.567')
  })

  it('groups thousands with a comma for English', () => {
    expect(formatCount(1234, 'en')).toBe('1,234')
    expect(formatCount(1234, 'en-US')).toBe('1,234')
  })

  it('leaves small numbers unseparated', () => {
    expect(formatCount(0, 'vi')).toBe('0')
    expect(formatCount(12, 'en')).toBe('12')
  })
})
