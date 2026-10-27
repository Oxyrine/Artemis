import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useBatch } from './hooks'

const respond = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
const wrap = () => { const qc = new QueryClient(); return ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider> }

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }) })
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('useBatch polling', () => {
  it('gives up on a batch the server no longer has instead of polling it forever', async () => {
    const fetchMock = vi.fn(async () => respond(404, { error: 'not_found', detail: 'no batch BATCH-0001' }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useBatch('BATCH-0001'), { wrapper: wrap() })
    await waitFor(() => expect(result.current.isError).toBe(true))
    const calls = fetchMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(10_000) // ten polling intervals' worth
    expect(fetchMock.mock.calls.length).toBe(calls)
    expect(calls).toBe(1) // and a 404 is not retried either
  })

  it('keeps polling while the batch runs and stops once it has finished', async () => {
    let running = true
    const fetchMock = vi.fn(async () => respond(200, { batch_id: 'BATCH-0001', running, done: 1, total: 2, errors: {}, mode: 'demo', replay: false }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useBatch('BATCH-0001'), { wrapper: wrap() })
    await waitFor(() => expect(result.current.data?.running).toBe(true))
    await vi.advanceTimersByTimeAsync(3_100)
    expect(fetchMock.mock.calls.length).toBeGreaterThan(2)
    running = false
    await waitFor(() => expect(result.current.data?.running).toBe(false), { timeout: 3000 })
    const calls = fetchMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(5_000)
    expect(fetchMock.mock.calls.length).toBe(calls)
  })
})
