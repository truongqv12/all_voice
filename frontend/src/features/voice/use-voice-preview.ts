import { useEffect, useRef, useState } from 'react'
import { useTtsApi } from '../../api/api-context'
import type { Voice } from '../../api/types'
import { claimAudio } from '../../lib/audio-playback-coordinator'

export function useVoicePreview() {
  const api = useTtsApi()
  const audio = useRef<HTMLAudioElement | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null); const request = useRef(0); const release = useRef<(() => void) | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  useEffect(() => () => { request.current += 1; audio.current?.pause(); release.current?.() }, [])
  async function toggle(voice: Voice) {
    if (activeId === voice.id) { request.current += 1; audio.current?.pause(); release.current?.(); setLoadingId(null); setActiveId(null); return }
    const requestId = ++request.current; audio.current?.pause(); release.current?.(); setLoadingId(voice.id)
    try { const src = await api.getPreviewUrl(voice); if (requestId !== request.current) return; const player = new Audio(src); audio.current = player
      release.current = claimAudio(() => { player.pause(); setActiveId(null) }); player.onended = () => { release.current?.(); setActiveId(null) }
      await player.play(); if (requestId === request.current) setActiveId(voice.id)
    } catch { if (requestId === request.current) setActiveId(null) } finally { if (requestId === request.current) setLoadingId(null) }
  }
  return { activeId, loadingId, toggle }
}
