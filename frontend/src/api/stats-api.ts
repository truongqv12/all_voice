import type { UsageStats } from './types'

export interface StatsApi {
  getStats(signal?: AbortSignal): Promise<UsageStats>
}

export const mockStatsApi: StatsApi = {
  async getStats() {
    return { active: 12, total: 1234 }
  },
}
