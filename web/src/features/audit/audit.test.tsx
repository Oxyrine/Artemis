import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuditPage } from './AuditPage'

const verify = vi.fn()
const tamperMutate = vi.fn()
const reset = vi.fn()
let verifyData: unknown, tamperData: unknown, tamperError: unknown
vi.mock('@/api/hooks', () => ({
  useAudit: () => ({ data: { events: [{ seq: 3, created_at: '2026-10-27T10:00:00Z', actor: 'system', event_type: 'AUTO_CLOSED', case_id: 'CASE-0001', hash: 'a'.repeat(64) },
    { seq: 4, created_at: '2026-10-27T10:00:01Z', actor: 'agent', event_type: 'GRADED', case_id: 'CASE-0007', hash: 'b'.repeat(64) }] }, isLoading: false, error: null, dataUpdatedAt: 1 }),
  useVerify: () => ({ mutate: verify, data: verifyData, error: null, isPending: false }),
  useTamper: () => ({ mutate: tamperMutate, data: tamperData, error: tamperError, isPending: false }),
  useReset: () => ({ mutate: reset, error: null, isPending: false }),
}))

beforeEach(() => { vi.clearAllMocks(); verifyData = undefined; tamperData = undefined; tamperError = null; Element.prototype.scrollIntoView = vi.fn() })

describe('Tamper demo', () => {
  it('verifies straight after tampering so the break shows up without a second click', async () => {
    tamperMutate.mockImplementation((_v: unknown, o: { onSuccess: () => void }) => o.onSuccess())
    render(<AuditPage />)
    await userEvent.click(screen.getByRole('button', { name: /Simulate tampering/ }))
    expect(tamperMutate).toHaveBeenCalledTimes(1)
    expect(verify).toHaveBeenCalledTimes(1)
  })

  it('says what was edited, highlights the broken event and scrolls to it', () => {
    tamperData = { seq: 3, field: 'amount_paise', before: 52_864_000, after: 52_964_000 }
    verifyData = { ok: false, first_broken_seq: 3, checked: 2, checkpoints: 0, reason: 'hash mismatch at event 3' }
    render(<AuditPage />)
    expect(screen.getByTestId('tamper-result')).toHaveTextContent('Event #3: amount_paise changed from ₹5,28,640 to ₹5,29,640')
    expect(screen.getByTestId('verify-broken')).toHaveTextContent('Chain broken at event #3')
    expect(document.getElementById('event-3')).toHaveClass('row-broken')
    expect(document.getElementById('event-4')).not.toHaveClass('row-broken')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  })

  it('reset heals the chain and re-verifies', async () => {
    reset.mockImplementation((_v: unknown, o: { onSuccess: () => void }) => o.onSuccess())
    render(<AuditPage />)
    await userEvent.click(screen.getByRole('button', { name: /Reset environment/ }))
    expect(reset).toHaveBeenCalledTimes(1)
    expect(verify).toHaveBeenCalledTimes(1)
  })

  it('shows the server’s reason when the demo is disabled', () => {
    tamperError = new Error('the tamper demo is disabled on this server')
    render(<AuditPage />)
    expect(screen.getByRole('alert')).toHaveTextContent('the tamper demo is disabled on this server')
  })
})
