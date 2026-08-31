import { createContext, useContext } from 'react'
import type { ReactNode } from 'react'
import { appConfig } from '../config/app-config'
import { mockTtsApi } from './mock-tts-api'
import { mockTranscribeApi } from './mock-transcribe-api'
import { mockCloneApi } from './clone-api'
import { mockStatsApi } from './stats-api'
import { httpTtsApi } from './http-tts-api'
import { httpTranscribeApi } from './http-transcribe-api'
import { httpCloneApi } from './http-clone-api'
import { httpStatsApi } from './http-stats-api'
import type { TtsApi } from './tts-api'
import type { TranscribeApi } from './transcribe-api'
import type { CloneApi } from './clone-api'
import type { StatsApi } from './stats-api'

export interface ApiContextValue {
  ttsApi: TtsApi
  transcribeApi: TranscribeApi
  cloneApi: CloneApi
  statsApi: StatsApi
}

const defaultContextValue: ApiContextValue = {
  ttsApi: appConfig.useMock ? mockTtsApi : httpTtsApi,
  transcribeApi: appConfig.useMock ? mockTranscribeApi : httpTranscribeApi,
  cloneApi: appConfig.useMock ? mockCloneApi : httpCloneApi,
  statsApi: appConfig.useMock ? mockStatsApi : httpStatsApi,
}

const ApiContext = createContext<ApiContextValue | null>(null)

export function ApiProvider({
  children,
  ttsApi,
  transcribeApi,
  cloneApi,
  statsApi,
}: {
  children: ReactNode
  ttsApi?: TtsApi
  transcribeApi?: TranscribeApi
  cloneApi?: CloneApi
  statsApi?: StatsApi
}) {
  const value: ApiContextValue = {
    ttsApi: ttsApi || defaultContextValue.ttsApi,
    transcribeApi: transcribeApi || defaultContextValue.transcribeApi,
    cloneApi: cloneApi || defaultContextValue.cloneApi,
    statsApi: statsApi || defaultContextValue.statsApi,
  }
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>
}

export function useTtsApi(): TtsApi {
  const ctx = useContext(ApiContext)
  if (!ctx) throw new Error('useTtsApi must be used inside ApiProvider')
  return ctx.ttsApi
}

export function useTranscribeApi(): TranscribeApi {
  const ctx = useContext(ApiContext)
  if (!ctx) throw new Error('useTranscribeApi must be used inside ApiProvider')
  return ctx.transcribeApi
}

export function useCloneApi(): CloneApi {
  const ctx = useContext(ApiContext)
  if (!ctx) throw new Error('useCloneApi must be used inside ApiProvider')
  return ctx.cloneApi
}

export function useStatsApi(): StatsApi {
  const ctx = useContext(ApiContext)
  if (!ctx) throw new Error('useStatsApi must be used inside ApiProvider')
  return ctx.statsApi
}
