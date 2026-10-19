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

  it('should map CapCut voices with deduced gender and trimmed names', async () => {
    vi.mocked(httpClient.apiJson).mockResolvedValueOnce({
      data: [
        {
          id: 'BV421_vivn_streaming',
          name: 'Nhỏ Ngọt Ngào',
          model: 'capcut',
          language: 'vi',
          preview_url: 'http://example.com/capcut-preview.mp3'
        },
        {
          id: 'BV075_streaming_vibrato_dsp',
          name: 'Việt Méo',
          model: 'capcut',
          language: 'vi',
        },
        {
          id: 'multi_male_felipe_uranus_bigtts',
          name: 'Giọng Nam Trầm ',
          model: 'capcut',
          language: 'vi',
        }
      ]
    })

    const voices = await httpTtsApi.listVoices()
    expect(voices).toHaveLength(3)
    expect(voices[0].engine).toBe('capcut')
    expect(voices[0].gender).toBe('female')
    expect(voices[0].previewUrl).toBe('http://example.com/capcut-preview.mp3')
    expect(voices[1].engine).toBe('capcut')
    expect(voices[1].gender).toBe('male')
    expect(voices[2].name).toBe('Giọng Nam Trầm')
    expect(voices[2].gender).toBe('male')
  })

  it('should synthesize CapCut voice with model="capcut" and no style', async () => {
    vi.mocked(httpClient.apiJson).mockResolvedValueOnce({
      data: [
        {
          id: 'BV421_vivn_streaming',
          name: 'Nhỏ Ngọt Ngào',
          model: 'capcut',
          language: 'vi',
        }
      ]
    })
    vi.mocked(httpClient.apiBlob).mockResolvedValueOnce(new Blob(['audio-data'], { type: 'audio/mpeg' }))

    await httpTtsApi.listVoices()
    await httpTtsApi.synth({
      text: 'Xin chào CapCut',
      voiceId: 'BV421_vivn_streaming',
      engine: 'capcut',
      style: '',
      speed: 1.1,
      format: 'mp3',
    })

    expect(httpClient.apiBlob).toHaveBeenCalledWith(
      '/audio/speech',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          model: 'capcut',
          input: 'Xin chào CapCut',
          voice: 'BV421_vivn_streaming',
          response_format: 'mp3',
          speed: 1.1,
        }),
      }),
    )
  })
})
