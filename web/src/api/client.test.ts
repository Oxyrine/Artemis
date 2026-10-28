import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('API availability failures', () => {
  it('turns the HTML 502 returned during a cold start into an actionable error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<h1>502</h1>', { status: 502 })))
    await expect(api('/cases')).rejects.toThrow('investigation service is temporarily unavailable')
  })

  it('ends a hanging request so a guide mutation cannot remain pending forever', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_url: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))
    const failed = expect(api('/batch/run', { method: 'POST', json: { mode: 'demo' } })).rejects.toThrow(/did not respond.*may still be running/i)
    await vi.advanceTimersByTimeAsync(30_000)
    await failed
  })

  it('preserves a policy refusal instead of disguising it as an availability failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'policy', detail: 'Probable cases cannot be approved.' }), { status: 409 })))
    await expect(api('/cases/CASE-0008/review', { method: 'POST' })).rejects.toThrow('Probable cases cannot be approved.')
  })
})
