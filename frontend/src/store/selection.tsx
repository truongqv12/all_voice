import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Voice } from '../api/types'
import { useTtsApi } from '../api/api-context'

interface SelectionState { voices: Voice[]; loading: boolean; error: boolean; selectedVoice: Voice | null; style: string; selectVoice(voice: Voice): void; addVoice(voice: Voice): void; removeVoice(id: string): void; setStyle(style: string): void; reload(): Promise<void> }
const SelectionContext = createContext<SelectionState | null>(null)

const CUSTOM_VOICES_KEY = 'all-voice-custom-voices'

function loadSavedCustomVoices(): Voice[] {
  try {
    const raw = localStorage.getItem(CUSTOM_VOICES_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveCustomVoices(items: Voice[]) {
  try {
    localStorage.setItem(CUSTOM_VOICES_KEY, JSON.stringify(items))
  } catch {
    // ignore
  }
}

export function SelectionProvider({ children }: { children: ReactNode }) {
  const api = useTtsApi()
  const [voices, setVoices] = useState<Voice[]>([])
  const [, setCustomVoices] = useState<Voice[]>(loadSavedCustomVoices)
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null)
  const [style, setStyle] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  async function reload() {
    setLoading(true)
    setError(false)
    try {
      const systemVoices = await api.listVoices()
      const saved = loadSavedCustomVoices()
      const next = [...systemVoices, ...saved]
      const refreshed = selectedVoice ? next.find(voice => voice.id === selectedVoice.id) : next[0]
      setVoices(next)
      setCustomVoices(saved)
      setSelectedVoice(refreshed ?? null)
      setStyle(current => (refreshed?.styles.includes(current) ? current : refreshed?.styles[0] ?? ''))
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void reload()
  }, [api])

  const value = useMemo(
    () => ({
      voices,
      loading,
      error,
      selectedVoice,
      style,
      setStyle,
      reload,
      addVoice: (voice: Voice) => {
        setCustomVoices(current => {
          const updated = [...current.filter(item => item.id !== voice.id), voice]
          saveCustomVoices(updated)
          return updated
        })
        setVoices(current => [...current.filter(item => item.id !== voice.id), voice])
      },
      removeVoice: (id: string) => {
        setCustomVoices(current => {
          const updated = current.filter(voice => voice.id !== id)
          saveCustomVoices(updated)
          return updated
        })
        setVoices(current => current.filter(voice => voice.id !== id))
        setSelectedVoice(current => (current?.id === id ? null : current))
      },
      selectVoice: (voice: Voice) => {
        setSelectedVoice(voice)
        setStyle(voice.styles[0] ?? '')
      },
    }),
    [voices, loading, error, selectedVoice, style]
  )

  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>
}

export function useSelection(): SelectionState {
  const selection = useContext(SelectionContext)
  if (!selection) throw new Error('useSelection must be used inside SelectionProvider')
  return selection
}
