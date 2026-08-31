import { apiJson } from './http-client'
import type { StatsApi } from './stats-api'
import type { UsageStats } from './types'

export const httpStatsApi: StatsApi = {
  getStats(signal) {
    // Short timeout: a gauge should fail fast and stay silent, never hang the poll.
    return apiJson<UsageStats>('/stats', { signal, timeoutMs: 8000 })
  },
}
