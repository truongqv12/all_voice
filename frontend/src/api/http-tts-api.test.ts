import { describe, expect, it, vi, beforeEach } from 'vitest'
import { httpTtsApi } from './http-tts-api'
import * as httpClient from './http-client'

vi.mock('./http-client', () => ({
  apiJson: vi.fn(),
  apiBlob: vi.fn(),
  apiFetch: vi.fn()
}))

describe('httpTtsApi', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('should map API response to Voice objects', async () => {
    vi.mocked(httpClient.apiJson).mockResolvedValueOnce({
      data: [
        {
          id: '1',
          name: 'Voice 1',
          model: 'vieneu',
          language: 'vi',
          styles: ['sad', 'happy'],
          preview_url: 'http://example.com/preview'
        }
      ]
    })

    const voices = await httpTtsApi.listVoices()
    expect(voices).toHaveLength(1)
    expect(voices[0].id).toBe('1')
    expect(voices[0].engine).toBe('vieneu')
    expect(voices[0].gender).toBe('neutral')
    expect(voices[0].styles).toEqual(['sad', 'happy'])
    expect(voices[0].previewUrl).toBe('http://example.com/preview')
  })
})
