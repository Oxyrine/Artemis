import type { CaseDetail, ReviewerActions } from '@/api/types'

const allowed = { allowed: true, reason: null }
export const analystAllowed: ReviewerActions = {
  reviewer_id: 'analyst-1', name: 'Asha Analyst', role: 'analyst', approve: allowed, request_evidence: allowed, reject: allowed,
}
export const controllerAllowed: ReviewerActions = { ...analystAllowed, reviewer_id: 'controller-1', name: 'Chandra Controller', role: 'controller' }

const blocked = (reason: string) => ({ allowed: false, reason })
export const probableActions = (reason = 'Probable: waiting for the missing evidence (e.g. the TDS certificate).'): ReviewerActions[] =>
  [analystAllowed, controllerAllowed].map((a) => ({ ...a, approve: blocked(reason), request_evidence: blocked(reason), reject: blocked(reason) }))

/** The hero case, as the API returns it: closes to zero, TDS 26,000 booked, ready for approval. */
export const heroDetail: CaseDetail = {
  schema_version: 1, case_id: 'CASE-0007', state: 'PENDING_APPROVAL', status: 'VERIFIED', customer_id: 'CUST-014',
  customer_name: 'ABC Infra Private Limited',
  receipts: [{ utr: 'UTR839201', value_date: '2026-09-12', amount_paise: 150_800_000, payer_name_raw: 'ABC INFRA PVT L',
    narration: 'NEFT/UTR839201/ABC INFRA PVT L/INV-1042/INV-1043', bank_charges_paise: 0, resolution_score: 100 }],
  invoices: [], allocations: [{ invoice_id: 'INV-1042', amount_paise: 118_000_000 }, { invoice_id: 'INV-1043', amount_paise: 35_400_000 }],
  adjustments: [{ kind: 'tds', amount_paise: 2_600_000, validated: true, validated_by_rule: 'tds equals compute_withholding', evidence_ids: ['EV-0001'] }],
  evidence: [], grade: { status: 'VERIFIED', flags: [], duplicate: false, recommendation: null },
  closure: { invoiced_paise: 153_400_000, adjustments: [{ kind: 'tds', amount_paise: 2_600_000, validated: true }],
    expected_paise: 150_800_000, received_paise: 150_800_000, unexplained_paise: 0 },
  proposed_entries: [
    { kind: 'allocation', invoice_id: 'INV-1042', account: null, amount_paise: 118_000_000 },
    { kind: 'allocation', invoice_id: 'INV-1043', account: null, amount_paise: 35_400_000 },
    { kind: 'adjustment', invoice_id: null, account: 'TDS receivable', amount_paise: 2_600_000 },
  ],
  narrative: 'Receipt UTR839201 matched.', narrative_source: 'template', run: null,
  actions: [analystAllowed, controllerAllowed],
}
