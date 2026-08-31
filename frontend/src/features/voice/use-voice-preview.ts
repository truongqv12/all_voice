import { useEffect, useRef, useState } from 'react'
import { useTtsApi } from '../../api/api-context'
import type { Voice } from '../../api/types'
import { claimAudio } from '../../lib/audio-playback-coordinator'

export function useVoicePreview() {
  const api = useTtsApi()
  const audio = useRef<HTMLAudioElement | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const request = useRef(0)
  const release = useRef<(() => void) | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      request.current += 1
      audio.current?.pause()
      release.current?.()
    }
  }, [])

  async function playAudioSrc(src: string, requestId: number) {
    if (requestId !== request.current) return false;
    const player = new Audio(src);
    audio.current = player;
    release.current = claimAudio(() => { player.pause(); setActiveId(null) });
    player.onended = () => { release.current?.(); setActiveId(null) };
    
    await player.play();
    return true;
  }

  async function toggle(voice: Voice) {
    if (activeId === voice.id) {
      request.current += 1
      audio.current?.pause()
      release.current?.()
      setLoadingId(null)
      setActiveId(null)
      return
    }

    const requestId = ++request.current
    audio.current?.pause()
    release.current?.()
    setLoadingId(voice.id)

    try {
      const src = await api.getPreviewUrl(voice)
      if (requestId !== request.current) return
      
      try {
        const played = await playAudioSrc(src, requestId);
        if (played && requestId === request.current) setActiveId(voice.id);
      } catch (playError) {
        // Fallback to synth if preview URL fails (e.g. 404 from backend)
        if (requestId !== request.current) return;
        
        try {
          const sampleText = voice.language === 'vi' ? 'Xin chào, đây là giọng đọc thử của tôi.' : 'Hello, this is a sample of my voice.';
          const result = await api.synth({
            text: sampleText,
            voiceId: voice.id,
            style: voice.styles[0] || 'default',
            speed: 1.0,
            format: 'mp3'
          });
          
          if (requestId !== request.current) return;
          const fallbackPlayed = await playAudioSrc(result.audioUrl, requestId);
          if (fallbackPlayed && requestId === request.current) setActiveId(voice.id);
        } catch (synthError) {
          if (requestId === request.current) setActiveId(null);
        }
      }
    } catch {
      if (requestId === request.current) setActiveId(null)
    } finally {
      if (requestId === request.current) setLoadingId(null)
    }
  }

  return { activeId, loadingId, toggle }
}
