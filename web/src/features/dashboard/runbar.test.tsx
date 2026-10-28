import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BatchProvider } from './BatchProvider'
import { RunBar } from './RunBar'

let states: string[] = []
let batchResult: { data?: unknown; error?: unknown } = {}
const runMutate = vi.fn()
vi.mock('@/api/hooks', () => ({
  useModes: () => ({ data: { modes: [{ mode: 'demo', label: 'Demo agent', available: true, reason: null }, { mode: 'replay', label: 'Replay', available: true, reason: null }] } }),
  useRunBatch: () => ({ mutate: runMutate, isPending: false, error: null }),
  useReset: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useBatch: () => batchResult,
  useCases: () => ({ data: { cases: states.map((state) => ({ state })) } }),
}))

const page = () => render(<QueryClientProvider client={new QueryClient()}><BatchProvider><RunBar /></BatchProvider></QueryClientProvider>)

beforeEach(() => { states = []; batchResult = {}; runMutate.mockReset() })

describe('RunBar', () => {
  it('offers Run batch while some case has not been investigated', () => {
    states = ['AUTO_CLOSED', 'NEW']
    page()
    expect(screen.getByRole('button', { name: /Run batch/ })).toBeEnabled()
    expect(screen.queryByText(/already been investigated/)).not.toBeInTheDocument()
  })

  it('disables Run batch and says why once every case has been investigated (the server would answer 409)', () => {
    states = ['AUTO_CLOSED', 'PENDING_APPROVAL', 'NEEDS_REVIEW']
    page()
    expect(screen.getByRole('button', { name: /Run batch/ })).toBeDisabled()
    expect(screen.getByText(/Reset the environment to run the batch again/)).toBeInTheDocument()
  })

  it('does not disable it before the case list has loaded', () => {
    page()
    expect(screen.getByRole('button', { name: /Run batch/ })).toBeEnabled()
  })

  it('explains it when the server forgot a batch it was running (a restart mid-run)', async () => {
    states = ['NEW']
    runMutate.mockImplementation((_mode: string, o: { onSuccess: (d: { batch_id: string }) => void }) => o.onSuccess({ batch_id: 'BATCH-0001' }))
    const { rerender } = page()
    await userEvent.click(screen.getByRole('button', { name: /Run batch/ }))
    batchResult = { error: new Error('no batch BATCH-0001') } // the server restarted and no longer knows it
    rerender(<QueryClientProvider client={new QueryClient()}><BatchProvider><RunBar /></BatchProvider></QueryClientProvider>)
    expect(await screen.findByText(/Could not continue tracking this batch/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Run batch/ })).toBeEnabled() // and offers to carry on
  })

  it('does not claim a restart for a stale error after a reset: that batch was not running any more', () => {
    states = ['NEW']
    batchResult = { error: new Error('no batch BATCH-0001') } // nothing was started in this session
    page()
    expect(screen.queryByText(/Could not continue tracking this batch/)).not.toBeInTheDocument()
  })
})
