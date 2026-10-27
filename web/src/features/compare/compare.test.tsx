import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { TraceView } from '@/api/types'
import { ComparePage } from './ComparePage'

const traces: Record<string, TraceView | undefined> = {}
vi.mock('@/api/hooks', () => ({
  useTrace: (id: string) => ({ data: traces[id], isLoading: false }),
  useCase: (id: string) => ({ data: { 'CASE-0007': { status: 'VERIFIED', state: 'PENDING_APPROVAL', grade: { flags: [] } },
    'CASE-0008': { status: 'PROBABLE', state: 'AWAITING_EVIDENCE', grade: { flags: [] } },
    'CASE-0009': { status: 'CONFLICTING', state: 'NEEDS_REVIEW', grade: { flags: [{}] } } }[id] }),
}))

const trace = (id: string, tools: string[], extract: unknown[]): TraceView => ({
  case_id: id, replay: false, tool_path: tools,
  steps: [{ step: 1, hypotheses: [{ id: 'H1', kind: 'tds', status: 'open', text: 'find out why' }],
    tool_calls: [{ id: 'T1', tool_name: 'compute_withholding', args_json: {}, result_json: { expected_paise: 2_600_000 }, latency_ms: 0 },
      { id: 'T2', tool_name: 'get_authorized_tax_credit_extract', args_json: {}, result_json: { rows: extract }, latency_ms: 0 }] }],
}) as unknown as TraceView

const page = () => render(<MemoryRouter><ComparePage /></MemoryRouter>)
beforeEach(() => { for (const k of Object.keys(traces)) delete traces[k] })

describe('ComparePage', () => {
  it('asks for a batch run when the traces do not exist yet', () => {
    page()
    expect(screen.getByRole('heading', { name: 'Run the batch first' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Go to the dashboard/ })).toHaveAttribute('href', '/')
  })

  it('shows what each run found and how the paths differ', () => {
    traces['CASE-0007'] = trace('CASE-0007', ['record_hypothesis', 'get_authorized_tax_credit_extract', 'finish'], [{ amount_credited: 2_600_000, deductor_name: 'ABC Infra' }])
    traces['CASE-0008'] = trace('CASE-0008', ['record_hypothesis', 'get_authorized_tax_credit_extract', 'request_evidence', 'finish'], [])
    traces['CASE-0009'] = trace('CASE-0009', ['record_hypothesis', 'get_authorized_tax_credit_extract', 'finish', 'record_hypothesis'], [{ amount_credited: 2_000_000, deductor_name: 'Orion' }])
    page()
    expect(screen.getByRole('status')).toHaveTextContent('3 cases, 3 different tool sequences')
    const cols = screen.getAllByRole('article')
    expect(cols).toHaveLength(3)
    expect(within(cols[0]).getAllByText('₹26,000')).toHaveLength(2) // computed TDS and the extract row: they match
    expect(within(cols[2]).getByText('₹20,000')).toBeInTheDocument() // the conflicting twin's extract differs from the ₹26,000 computed
    expect(within(cols[2]).getAllByText('₹26,000')).toHaveLength(1)
    expect(within(cols[1]).getByText('Nothing filed')).toBeInTheDocument()
    expect(within(cols[0]).getByText(/Not called here/).closest('p')).toHaveTextContent('Ask for the missing evidence') // only the Probable twin asked
    expect(within(cols[1]).queryByText(/Not called here/)).not.toBeInTheDocument() // it did everything the others did
    expect(within(cols[1]).getByText('Ask for the missing evidence')).toBeInTheDocument()
    expect(within(cols[2]).getByText('No: 1 contradiction')).toBeInTheDocument()
    expect(within(cols[0]).getByText('Yes')).toBeInTheDocument()
    expect(within(cols[0]).getByText(/Why Verified/)).toBeInTheDocument()
  })
})
