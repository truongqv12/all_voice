import { useCallback, useEffect, useRef, useState } from 'react'

export function useTranscriptPlayback() {
  const audio = useRef<HTMLAudioElement | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const setAudioRef = useCallback((element: HTMLAudioElement | null) => { if (!element && audio.current) audio.current.pause(); audio.current = element }, [])
  useEffect(() => () => { audio.current?.pause() }, [])
  return { audioRef: setAudioRef, currentTime, onTimeUpdate: (event: React.SyntheticEvent<HTMLAudioElement>) => setCurrentTime(event.currentTarget.currentTime) }
}
