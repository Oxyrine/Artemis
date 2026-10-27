import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CaseDetail } from '@/api/types'
import { heroDetail, probableActions } from '@/test/fixtures'
import { ClosureCard } from './ClosureCard'
import { ContradictionPanel } from './EvidencePanels'
import { layoutGraph } from './graphLayout'
import { ReviewerPanel } from './ReviewerPanel'

const mutate = vi.fn()
vi.mock('@/api/hooks', () => ({
  useReviewers: () => ({ data: [
    { id: 'analyst-1', name: 'Asha Analyst', role: 'analyst', approval_limit_paise: 100_000_000 },
    { id: 'controller-1', name: 'Chandra Controller', role: 'controller', approval_limit_paise: null }] }),
  useReview: () => ({ mutate, isPending: false, error: null }),
  useAudit: () => ({ data: { events: [] } }),
}))

beforeEach(() => mutate.mockClear())

describe('ClosureCard (the Slide 5 layout)', () => {
  it('shows invoiced, minus each adjustment, expected, received and a zero in large type', () => {
    render(<ClosureCard closure={heroDetail.closure!} />)
    expect(screen.getByText('15,34,000')).toBeInTheDocument()
    expect(screen.getByText('− TDS')).toBeInTheDocument()
    expect(screen.getAllByText('15,08,000')).toHaveLength(2) // expected and received
    expect(screen.getByTestId('unexplained')).toHaveTextContent('₹0')
    expect(screen.getByText(/closes to zero/)).toBeInTheDocument()
  })
  it('flags an unexplained amount and struck-through unvalidated adjustments', () => {
    render(<ClosureCard closure={{ ...heroDetail.closure!, unexplained_paise: 2_600_000,
      adjustments: [{ kind: 'tds', amount_paise: 2_600_000, validated: false }] }} />)
    expect(screen.getByTestId('unexplained')).toHaveTextContent('₹26,000')
    expect(screen.getByText(/not validated/)).toBeInTheDocument()
    expect(screen.getByText(/not explained by any validated adjustment/)).toBeInTheDocument()
  })
})

describe('ContradictionPanel', () => {
  it('puts the two disagreeing items side by side and highlights the differing values', () => {
    render(<ContradictionPanel flags={[{ code: 1, detail: 'tax credit 2000000 vs computed 2600000 (paise)',
      a: { ref: 'EV-0001', kind: 'withholding_calc', excerpt: '', amount_paise: 2_600_000 },
      b: { ref: 'EV-0002', kind: 'tax_credit', excerpt: 'Orion Civil Limited', amount_paise: 2_000_000 } }]} />)
    const amounts = screen.getAllByTestId('flag-amount')
    expect(amounts.map((a) => a.textContent)).toEqual(['₹26,000', '₹20,000'])
    amounts.forEach((a) => expect(a.className).toContain('status-conflicting'))
  })
  it('renders nothing when there are no flags', () => {
    const { container } = render(<ContradictionPanel flags={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('ReviewerPanel', () => {
  it('lets the analyst approve the hero case, and requires a comment for the other actions', async () => {
    render(<ReviewerPanel detail={heroDetail} />)
    expect(screen.getByRole('button', { name: 'Approve' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Request evidence' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled()
    expect(screen.getAllByText('A comment is required for this action.')).toHaveLength(2)

    await userEvent.type(screen.getByLabelText(/Comment/), 'need the TDS certificate')
    expect(screen.getByRole('button', { name: 'Request evidence' })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(mutate).toHaveBeenCalledWith({ reviewer: 'analyst-1', decision: 'approve', comment: 'need the TDS certificate' }, expect.anything())
  })

  it('shows the proposed entries, including where the adjustment is booked', () => {
    render(<ReviewerPanel detail={heroDetail} />)
    expect(screen.getByText('Apply receipt to INV-1042')).toBeInTheDocument()
    expect(screen.getByText('Book to TDS receivable')).toBeInTheDocument()
    expect(screen.getByText('26,000')).toBeInTheDocument()
  })

  it('disables a blocked action and shows the policy reason beneath it', () => {
    const probable: CaseDetail = { ...heroDetail, state: 'AWAITING_EVIDENCE', status: 'PROBABLE', actions: probableActions() }
    render(<ReviewerPanel detail={probable} />)
    const approve = screen.getByRole('button', { name: 'Approve' })
    expect(approve).toBeDisabled()
    const reasonId = approve.getAttribute('aria-describedby')!
    expect(document.getElementById(reasonId)).toHaveTextContent('Probable: waiting for the missing evidence')
  })

  it('asks for confirmation before rejecting, and shows the comment being recorded', async () => {
    render(<ReviewerPanel detail={heroDetail} />)
    await userEvent.type(screen.getByLabelText(/Comment/), 'duplicate of another receipt')
    await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Reject CASE-0007?')).toBeInTheDocument()
    expect(within(dialog).getByText('duplicate of another receipt')).toBeInTheDocument()
    expect(mutate).not.toHaveBeenCalled() // nothing is sent until the reviewer confirms
    await userEvent.click(within(dialog).getByRole('button', { name: 'Reject case' }))
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ decision: 'reject' }), expect.anything())
  })

  it('keeps the confirmation visible after the approval moves the case out of the reviewable states', async () => {
    const { rerender } = render(<ReviewerPanel detail={heroDetail} />)
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    act(() => mutate.mock.calls[0][1].onSuccess({ state: 'APPLIED', audit_seq: 573 }))
    rerender(<ReviewerPanel detail={{ ...heroDetail, state: 'APPLIED' }} />)
    expect(screen.getByRole('status')).toHaveTextContent(/recorded by Asha Analyst.*audit event #573/)
  })

  it('offers no actions once the case is applied', () => {
    render(<ReviewerPanel detail={{ ...heroDetail, state: 'APPLIED' }} />)
    expect(screen.getByText(/no review action is available/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  })
})

describe('layoutGraph', () => {
  it('lays the graph out left to right: each edge points rightwards', () => {
    const pos = layoutGraph({ schema_version: 1, case_id: 'C',
      nodes: [{ id: 'r', kind: 'receipt', label: 'r' }, { id: 'i', kind: 'invoice', label: 'i' }, { id: 'a', kind: 'adjustment', label: 'a' }] as never,
      edges: [{ id: 'e1', source: 'r', target: 'i', kind: 'allocates' }, { id: 'e2', source: 'a', target: 'i', kind: 'adjusts' }] as never })
    expect(pos.r.x).toBeLessThan(pos.i.x)
    expect(pos.a.x).toBeLessThan(pos.i.x)
    expect(Object.values(pos).every((p) => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true)
  })
})
