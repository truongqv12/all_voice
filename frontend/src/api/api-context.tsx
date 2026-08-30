import { createContext, useContext } from 'react'
import type { ReactNode } from 'react'
import { mockTtsApi } from './mock-tts-api'
import type { TtsApi } from './tts-api'

const TtsApiContext = createContext<TtsApi | null>(null)

export function ApiProvider({ children, ttsApi = mockTtsApi }: { children: ReactNode; ttsApi?: TtsApi }) {
  return <TtsApiContext.Provider value={ttsApi}>{children}</TtsApiContext.Provider>
}

export function useTtsApi(): TtsApi {
  const api = useContext(TtsApiContext)
  if (!api) throw new Error('useTtsApi must be used inside ApiProvider')
  return api
}
