import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { CaseSummary } from '@/api/types'
import { filterCases, VarianceBridge } from './DashboardPage'

const rows: CaseSummary[] = [
  { case_id: 'CASE-0007', customer_name: 'ABC Infra Private Limited', customer_id: 'CUST-014', utrs: ['UTR839201', 'UTR839202'], receipt_paise: 150800000, variance_paise: null, unexplained_paise: null, duplicate: false, status: null, state: 'NEW', steps: null },
  { case_id: 'CASE-0008', customer_name: null, customer_id: null, utrs: ['UTR839203'], receipt_paise: 150800000, variance_paise: null, unexplained_paise: null, duplicate: false, status: null, state: 'NEW', steps: null },
]

describe('Receipt queue search', () => {
  it('matches customer, case and every UTR, ignoring case and surrounding whitespace', () => {
    for (const query of [' abc infra ', 'case-0007', 'utr839202']) {
      expect(filterCases(rows, query).map((c) => c.case_id)).toEqual(['CASE-0007'])
    }
  })
  it('handles unresolved customers and restores the full queue when cleared', () => {
    expect(filterCases(rows, 'UTR839203')).toEqual([rows[1]])
    expect(filterCases(rows, 'unknown')).toEqual([])
    expect(filterCases(rows, '  ')).toEqual(rows)
  })
})

describe('Variance bridge', () => {
  it('describes the real explained and held proportions, with honest empty and unavailable states', () => {
    const { rerender } = render(<VarianceBridge investigated={40000} explained={10000} held={30000} />)
    expect(screen.getByRole('img')).toHaveAccessibleName('25% of reported variance explained; 75% held for evidence or review')
    rerender(<VarianceBridge investigated={0} explained={0} held={0} />)
    expect(screen.getByRole('img')).toHaveAccessibleName('No variance investigated yet')
    rerender(<VarianceBridge />)
    expect(screen.getByRole('img')).toHaveAccessibleName('Variance data unavailable')
  })
})
