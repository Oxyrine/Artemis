// Plain-language content for people who have never seen accounts-receivable reconciliation: the glossary, the grade
// explanations, the tool labels and the guided-demo script. Figures about the hero case are pinned by the build spec
// (the generator asserts them), so they are written here once and formatted by lib/format.

/** The hero case and its two twins (spec: "the hero case and both twins show three different tool paths"). */
export const HERO_CASE = 'CASE-0007'
export const TWIN_CASES = { probable: 'CASE-0008', conflicting: 'CASE-0009' } as const
export const SHOWCASE = [
  { caseId: HERO_CASE, role: 'The hero case', lead: 'The tax credit is there and matches' },
  { caseId: TWIN_CASES.probable, role: 'Twin: evidence missing', lead: 'The tax credit has not been filed yet' },
  { caseId: TWIN_CASES.conflicting, role: 'Twin: sources disagree', lead: 'The tax credit shows a different amount' },
] as const

export const HERO_FACTS = { invoiced_paise: 153_400_000, received_paise: 150_800_000, tds_paise: 2_600_000, utr: 'UTR839201' } as const

export const GLOSSARY = {
  reconciliation: ['Reconciliation', 'Matching each payment that arrives in the bank to the invoices it pays, and explaining any difference.'],
  utr: ['UTR', 'Unique Transaction Reference: the bank’s ID for one payment. Every receipt in this app is identified by its UTR.'],
  tds: ['TDS', 'Tax Deducted at Source. A customer may withhold a slice of an invoice (here 2%) and pay it to the tax department instead of to you. The money is not lost: it appears as a tax credit in your name.'],
  taxcredit: ['Tax credit extract', 'The tax department’s statement of the tax others have deposited on your behalf. It is the primary proof that withheld money really reached the government.'],
  variance: ['Variance', 'The difference between what the invoices add up to and what the bank actually received.'],
  unexplained: ['Unexplained', 'What is still unaccounted for after every adjustment that Artemis could validate against a rule or a document. Zero means the case closes.'],
  allocation: ['Allocation', 'Which invoices a receipt pays, and how much of each.'],
  adjustment: ['Adjustment', 'A validated reason for a gap between invoiced and received: tax withheld, a credit note, a bank charge or rounding.'],
  evidence: ['Evidence tiers', 'Primary: bank, ERP, issued credit notes and tax-department rows. Supporting: emails and purchase-order references. Derived: calculations and entity matches. Verified needs primary evidence.'],
  ledger: ['Audit ledger', 'An append-only log where every event carries the hash of the one before it, so changing any past event breaks every link after it.'],
} as const
export type TermKey = keyof typeof GLOSSARY

export const GRADE_NOTE: Record<string, { title: string; text: string }> = {
  AUTO_CLOSED: { title: 'Why auto-closed?', text: 'The payer matched at 95+ confidence, exactly one open invoice has the same amount, and the dates fit. Nothing was left to investigate.' },
  VERIFIED: { title: 'Why Verified?', text: 'The variance closes to zero, every adjustment is backed by at least one primary document, and no two sources disagree. A reviewer can approve it.' },
  PROBABLE: { title: 'Why only Probable?', text: 'The numbers close, but at least one adjustment rests on supporting evidence only (an email, not a tax record). Nobody can approve it until the missing evidence arrives.' },
  INSUFFICIENT: { title: 'Why Insufficient?', text: 'Even after every validated adjustment, money is still unexplained, or the receipt looks like a duplicate. Artemis refuses to clear it and hands it to an analyst.' },
  CONFLICTING: { title: 'Why Conflicting?', text: 'Two sources disagree (for example the email and the tax record). Artemis stops, shows the disagreeing pair, and will not approve until a person resolves it.' },
}

export const TOOL_LABEL: Record<string, string> = {
  record_hypothesis: 'Record a hypothesis',
  search_ledger: 'Look up open invoices',
  search_bank_receipts: 'Check bank receipts',
  search_remittance_email: 'Find the remittance email',
  parse_remittance: 'Read the email',
  get_authorized_tax_credit_extract: 'Check the tax-credit extract',
  compute_withholding: 'Compute expected TDS (rule engine)',
  find_credit_notes: 'Look for credit notes',
  resolve_customer: 'Resolve the customer',
  propose_allocation: 'Propose the allocation (engine validates)',
  request_evidence: 'Ask for the missing evidence',
  finish: 'Finish and hand over for grading',
}

/** Fired to reopen the dashboard explainer when a guide step points at it after the visitor dismissed it. */
export const WELCOME_EVENT = 'artemis:show-welcome'

export type GuideLink = { label: string; to: string; action?: 'run-batch' | 'show-welcome' }
export type GuideStep = { id: string; title: string; body: string; links: GuideLink[] }

/** The spec's five-minute demo script, as steps a visitor can follow without a presenter. */
export const GUIDE_STEPS: GuideStep[] = [
  { id: 'problem', title: 'The problem', links: [{ label: 'Show me', to: '/', action: 'show-welcome' }],
    body: 'A customer pays ₹15,08,000 against ₹15,34,000 of invoices. Where did the ₹26,000 go? Finance teams chase this one receipt at a time. Artemis does the legwork and shows its evidence.' },
  { id: 'batch', title: 'Run the batch', links: [{ label: 'Run it for me', to: '/', action: 'run-batch' }],
    body: 'Artemis matches payments to invoices, closes the exact ones itself, then sends an agent to investigate every exception. Watch the outcome tiles fill in.' },
  { id: 'hero', title: 'Open the hero case', links: [{ label: `Open ${HERO_CASE}`, to: `/cases/${HERO_CASE}` }],
    body: 'The ₹26,000 is tax the customer withheld. See the variance close to ₹0, the evidence graph that proves it, and the agent’s step-by-step trace.' },
  { id: 'twins', title: 'Same case, different evidence', links: [{ label: 'Compare the three paths', to: '/compare' }],
    body: 'Two near-identical twins: in one the tax credit is missing, in the other it shows a different amount. The agent takes a different path each time, and grades them Probable and Conflicting.' },
  { id: 'decide', title: 'A person decides', links: [{ label: `Approve ${HERO_CASE}`, to: `/cases/${HERO_CASE}` }, { label: 'Try the Probable twin', to: `/cases/${TWIN_CASES.probable}` }],
    body: 'Approve the hero case as the analyst. Then open the Probable twin: the policy blocks the approval and says why. The model never decides.' },
  { id: 'ledger', title: 'Break the ledger on purpose', links: [{ label: 'Go to the audit ledger', to: '/audit' }],
    body: 'Verify the chain, simulate tampering with one event, then verify again. The chain goes red at exactly the edited event. Reset the environment to heal it.' },
  { id: 'scoreboard', title: 'The scoreboard', links: [{ label: 'See the metrics', to: '/#metrics' }],
    body: 'Verified precision, abstention accuracy and tool-path diversity, measured against a hidden answer key. Zero false clears is the bar.' },
]
