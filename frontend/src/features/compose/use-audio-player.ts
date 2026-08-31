import { useCallback, useEffect, useRef, useState } from 'react'
import { claimAudio } from '../../lib/audio-playback-coordinator'

export function useAudioPlayer() {
  const media = useRef<HTMLAudioElement | null>(null); const release = useRef<(() => void) | null>(null); const claimed = useRef(false); const [playing, setPlaying] = useState(false)
  const setAudioRef = useCallback((element: HTMLAudioElement | null) => { if (!element && media.current) media.current.pause(); media.current = element }, [])
  function stop() { media.current?.pause(); const currentRelease = release.current; release.current = null; currentRelease?.(); claimed.current = false; setPlaying(false) }
  async function toggle() { const audio = media.current; if (!audio) return; if (audio.paused) { release.current = claimAudio(stop); claimed.current = true; await audio.play(); setPlaying(true) } else stop() }
  function markPlaying() { if (!claimed.current) { release.current = claimAudio(stop); claimed.current = true }; setPlaying(true) }
  useEffect(() => () => { stop() }, [])
  return { audioRef: setAudioRef, playing, toggle, stop, markPlaying }
}
