import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api/http-client'
import type { Voice } from '../../api/types'
import { useTtsApi } from '../../api/api-context'
import { claimAudio } from '../../lib/audio-playback-coordinator'

export function useVoicePreview() {
  const api = useTtsApi()
  const audio = useRef<HTMLAudioElement | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const request = useRef(0)
  const release = useRef<(() => void) | null>(null)
  const objectUrl = useRef<string | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [errorId, setErrorId] = useState<string | null>(null)

  function stopPlayback() {
    audio.current?.pause()
    const currentRelease = release.current
    release.current = null
    currentRelease?.()
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
    objectUrl.current = null
  }

  useEffect(() => {
    return () => {
      request.current += 1
      stopPlayback()
    }
  }, [])

  async function playAudioSrc(src: string, requestId: number) {
    if (requestId !== request.current) return false;
    // Bound the preview fetch so a hung endpoint cannot spin the loading state forever.
    const response = await fetch(src, { signal: AbortSignal.timeout(20_000) })
    if (!response.ok) throw new ApiError(response.status, response.status === 404 ? 'preview_not_found' : 'preview_load_failed', 'Preview could not be loaded.')
    const previewUrl = URL.createObjectURL(await response.blob())
    if (requestId !== request.current) {
      URL.revokeObjectURL(previewUrl)
      return false
    }
    objectUrl.current = previewUrl
    const player = new Audio(previewUrl);
    audio.current = player;
    release.current = claimAudio(() => { stopPlayback(); setActiveId(null) });
    player.onended = () => { stopPlayback(); setActiveId(null) };
    try {
      await player.play();
    } catch (error) {
      stopPlayback()
      throw error
    }
    return true;
  }

  async function toggle(voice: Voice) {
    if (activeId === voice.id) {
      request.current += 1
      stopPlayback()
      setLoadingId(null)
      setActiveId(null)
      return
    }

    const requestId = ++request.current
    stopPlayback()
    setLoadingId(voice.id)
    setErrorId(null)

    try {
      const src = await api.getPreviewUrl(voice)
      if (requestId !== request.current) return
      
      const played = await playAudioSrc(src, requestId);
      if (played && requestId === request.current) setActiveId(voice.id);
    } catch {
      if (requestId === request.current) {
        setActiveId(null)
        setErrorId(voice.id)
      }
    } finally {
      if (requestId === request.current) setLoadingId(null)
    }
  }

  return { activeId, loadingId, errorId, toggle }
}
