import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BatchProvider } from './BatchProvider'
import { RunBar } from './RunBar'

let states: string[] = []
vi.mock('@/api/hooks', () => ({
  useModes: () => ({ data: { modes: [{ mode: 'demo', label: 'Demo agent', available: true, reason: null }, { mode: 'replay', label: 'Replay', available: true, reason: null }] } }),
  useRunBatch: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useReset: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useBatch: () => ({ data: undefined }),
  useCases: () => ({ data: { cases: states.map((state) => ({ state })) } }),
}))

beforeEach(() => { states = [] })

describe('RunBar', () => {
  it('offers Run batch while some case has not been investigated', () => {
    states = ['AUTO_CLOSED', 'NEW']
    render(<BatchProvider><RunBar /></BatchProvider>)
    expect(screen.getByRole('button', { name: /Run batch/ })).toBeEnabled()
    expect(screen.queryByText(/already been investigated/)).not.toBeInTheDocument()
  })

  it('disables Run batch and says why once every case has been investigated (the server would answer 409)', () => {
    states = ['AUTO_CLOSED', 'PENDING_APPROVAL', 'NEEDS_REVIEW']
    render(<BatchProvider><RunBar /></BatchProvider>)
    expect(screen.getByRole('button', { name: /Run batch/ })).toBeDisabled()
    expect(screen.getByText(/Reset the environment to run the batch again/)).toBeInTheDocument()
  })

  it('does not disable it before the case list has loaded', () => {
    render(<BatchProvider><RunBar /></BatchProvider>)
    expect(screen.getByRole('button', { name: /Run batch/ })).toBeEnabled()
  })
})
