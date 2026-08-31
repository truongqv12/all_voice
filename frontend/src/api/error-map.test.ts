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
    expect(mapErrorToLimitKind(new ApiError(400, 'invalid_audio_file', ''))).toBe('audio-invalid')
    expect(mapErrorToLimitKind(new ApiError(400, 'audio_file_too_large', ''))).toBe('audio-too-large')
    expect(mapErrorToLimitKind(new ApiError(401, 'invalid_api_key', ''))).toBe('auth')
    expect(mapErrorToLimitKind(new ApiError(404, 'preview_not_found', ''))).toBe('no-preview')
    expect(mapErrorToLimitKind(new ApiError(503, 'asr_unavailable', ''))).toBe('asr-unavailable')
    expect(mapErrorToLimitKind(new ApiError(0, 'timeout', ''))).toBe('timeout')
  })

  it('should return null for unknown errors', () => {
    expect(mapErrorToLimitKind(new ApiError(500, 'internal_error', ''))).toBeNull()
    expect(mapErrorToLimitKind(new Error('Unknown'))).toBeNull()
  })
})
