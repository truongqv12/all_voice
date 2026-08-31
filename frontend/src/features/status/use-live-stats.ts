import { useEffect, useRef, useState } from 'react'
import { useStatsApi } from '../../api/api-context'
import type { UsageStats } from '../../api/types'

const POLL_INTERVAL_MS = 15_000

/**
 * Polls the public /v1/stats gauge on a fixed interval.
 *
 * - Pauses while the tab is hidden (no wasted requests in background tabs) and
 *   refetches immediately on re-focus.
 * - Aborts any in-flight request between polls and on unmount.
 * - Returns the last good value, or `null` before the first success. Errors are
 *   swallowed and the last value kept — a gauge must never surface an error.
 *
 * The effect runs once (empty deps) and reads the api through a ref, so a new
 * provider identity never tears down the interval or triggers a stale closure.
 */
export function useLiveStats(): UsageStats | null {
  const statsApi = useStatsApi()
  const [stats, setStats] = useState<UsageStats | null>(null)
  const apiRef = useRef(statsApi)
  apiRef.current = statsApi

  useEffect(() => {
    let cancelled = false
    let controller: AbortController | null = null
    let timer: ReturnType<typeof setInterval> | undefined

    const poll = async () => {
      controller?.abort()
      controller = new AbortController()
      try {
        const next = await apiRef.current.getStats(controller.signal)
        if (!cancelled) setStats(next)
      } catch {
        // Silent by design: keep the last good value, never render an error.
      }
    }

    const start = () => {
      if (timer !== undefined) return
      void poll()
      timer = setInterval(poll, POLL_INTERVAL_MS)
    }
    const stop = () => {
      if (timer !== undefined) clearInterval(timer)
      timer = undefined
      controller?.abort()
    }

    const onVisibility = () => {
      if (document.hidden) stop()
      else start()
    }

    if (!document.hidden) start()
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      cancelled = true
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return stats
}
