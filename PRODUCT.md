# Artemis

Visual preference: the user explicitly rejects repeated cards and badges as generic. Use open document sections, whitespace, table rules and column separators as the default. Reserve enclosed surfaces for controls that need containment, such as the evidence graph viewport, floating guide and confirmation dialogs. Omit case-header status/mode badges, the “Synthetic environment” header label and the “Receivables workspace / INR” sidebar strip. Keep synthetic-data disclosure in the footer and meaningful status text in the receipt queue and review explanation.

Artemis is a synthetic Indian accounts-receivable reconciliation workspace for analysts and controllers. Its deterministic core and investigating agent explain differences between bank receipts and invoices. Reviewers inspect evidence and make policy-controlled decisions, recorded in a hash-linked audit ledger.

The application supports 40 seeded cases, automatic exact matches, demo/replay/live investigation modes, case detail with variance closure and evidence graph, named reviewer decisions, evaluation metrics, and audit verification. Amounts are integer paise, formatted only in `web/src/lib/format.ts`. Tax rules are configured, not advised. Demo data and benchmark accuracy must stay explicitly identified as synthetic. Existing API contracts, approval limits, review comments, reset confirmation, and status meanings must survive a redesign.

Analysts work primarily at a desktop, scanning a queue then investigating exceptions. Mobile must support inspection and review without clipping controls. The surface is an operational tool: legibility, clear records, honest loading and errors, keyboard access, and evidence near decisions take priority.
