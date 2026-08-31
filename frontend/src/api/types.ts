export type VoiceLanguage = 'vi' | 'en' | 'ja'
export type VoiceGender = 'female' | 'male' | 'neutral'
export type AudioFormat = 'mp3' | 'wav'

export interface Voice {
  id: string
  name: string
  language: VoiceLanguage
  engine: 'vieneu' | 'kokoro' | 'voicevox' | 'clone'
  gender: VoiceGender
  age?: string
  styles: string[]
  description: string
  previewUrl?: string
}

export interface SynthParams {
  text: string
  voiceId: string
  engine?: Voice['engine']
  style: string
  speed: number
  format: AudioFormat
}

export interface SynthResult {
  audioUrl: string
  audioBlob: Blob
  filename: string
  previewOnly: boolean
  engine: Voice['engine']
}
