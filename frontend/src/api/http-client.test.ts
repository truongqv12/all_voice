import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiBlob, apiFetch } from './http-client'

describe('apiFetch', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('aborts and reports a timeout when the configured deadline elapses', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('localStorage', { getItem: () => null })
    vi.stubGlobal('fetch', (_url: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    }))

    const pending = apiFetch('/slow', { timeoutMs: 10 })
    const assertion = expect(pending).rejects.toMatchObject({ code: 'timeout', status: 0 })
    await vi.advanceTimersByTimeAsync(10)

    await assertion
  })

  it('keeps the deadline active while a response body is still streaming', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('localStorage', { getItem: () => null })
    vi.stubGlobal('fetch', (_url: string, init: RequestInit) => {
      const body = new ReadableStream({
        start(controller) {
          init.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')))
        },
      })
      return Promise.resolve(new Response(body))
    })

    const pending = apiBlob('/slow-body', { timeoutMs: 10 })
    const assertion = expect(pending).rejects.toMatchObject({ code: 'timeout', status: 0 })
    await vi.advanceTimersByTimeAsync(10)

    await assertion
  })
})
