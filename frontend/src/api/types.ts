export type VoiceLanguage = 'vi' | 'en' | 'ja'
export type VoiceGender = 'female' | 'male' | 'neutral'
export type AudioFormat = 'mp3' | 'wav' | 'ogg'

export interface Voice {
  id: string
  name: string
  language: VoiceLanguage
  engine: 'vieneu' | 'kokoro' | 'voicevox' | 'clone'
  gender: VoiceGender
  styles: string[]
  description: string
}

export interface SynthParams {
  text: string
  voiceId: string
  style: string
  speed: number
  format: AudioFormat
}

export interface SynthResult {
  audioUrl: string
  filename: string
  previewOnly: boolean
}
