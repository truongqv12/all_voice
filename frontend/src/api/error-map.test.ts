import { describe, expect, it } from 'vitest'
import { mapErrorToLimitKind } from './error-map'
import { ApiError } from './http-client'

describe('mapErrorToLimitKind', () => {
  it('should map HTTP status codes to LimitKind', () => {
    expect(mapErrorToLimitKind(new ApiError(413, '', ''))).toBe('asr-too-long')
    expect(mapErrorToLimitKind(new ApiError(429, '', ''))).toBe('rate')
    expect(mapErrorToLimitKind(new ApiError(402, '', ''))).toBe('quota')
    expect(mapErrorToLimitKind(new ApiError(503, '', ''))).toBe('overloaded')
  })

  it('should map specific error codes to LimitKind', () => {
    expect(mapErrorToLimitKind(new ApiError(400, 'rate_limit_exceeded', ''))).toBe('rate')
    expect(mapErrorToLimitKind(new ApiError(400, 'quota_exceeded', ''))).toBe('quota')
    expect(mapErrorToLimitKind(new ApiError(400, 'input_too_long', ''))).toBe('too-long')
    expect(mapErrorToLimitKind(new ApiError(400, 'server_overloaded', ''))).toBe('overloaded')
  })

  it('should return null for unknown errors', () => {
    expect(mapErrorToLimitKind(new ApiError(500, 'internal_error', ''))).toBeNull()
    expect(mapErrorToLimitKind(new Error('Unknown'))).toBeNull()
  })
})
