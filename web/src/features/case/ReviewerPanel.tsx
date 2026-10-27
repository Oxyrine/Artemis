import { useState } from 'react'
import { useAudit, useReview, useReviewers } from '@/api/hooks'
import type { CaseDetail, Decision } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { amount, humanize } from '@/lib/format'
import { useReviewer } from '@/app/providers'
import { AuditTable } from '@/features/audit/AuditTable'
import { ConfirmDialog, NativeSelect } from '@/ui/controls'
import { ErrorBanner, Section } from '@/ui/primitives'

const ACTIVE = ['PENDING_APPROVAL', 'AWAITING_EVIDENCE', 'NEEDS_REVIEW']
const NEEDS_COMMENT: Decision[] = ['reject', 'request_evidence']

/** A named reviewer approves, requests evidence or rejects. The server's policy decides; a blocked button is disabled and says why. */
export function ReviewerPanel({ detail }: { detail: CaseDetail }) {
  const reviewers = useReviewers()
  const { reviewerId, setReviewerId } = useReviewer()
  const review = useReview(detail.case_id)
  const audit = useAudit(detail.case_id)
  const [comment, setComment] = useState('')
  const [confirmReject, setConfirmReject] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const who = detail.actions.find((a) => a.reviewer_id === reviewerId) ?? detail.actions[0]
  const entries = detail.proposed_entries
  const missingComment = !comment.trim()

  function decide(decision: Decision) {
    setMessage(null)
    review.mutate({ reviewer: who.reviewer_id, decision, comment }, {
      onSuccess: (r) => { setComment(''); setConfirmReject(false); setMessage(`${humanize(decision)} recorded by ${who.name}. Case is now ${humanize(r.state)}; audit event #${r.audit_seq}.`) },
      onError: () => setConfirmReject(false),
    })
  }

  const action = (decision: Decision, label: string, a: { allowed: boolean; reason?: string | null }, variant: 'default' | 'outline' | 'destructive', onClick: () => void) => {
    const blockedByComment = NEEDS_COMMENT.includes(decision) && missingComment
    const reason = !a.allowed ? a.reason : blockedByComment ? 'A comment is required for this action.' : null
    return (
      <div className="flex flex-col gap-1">
        <Button variant={variant} disabled={!a.allowed || blockedByComment || review.isPending} aria-describedby={reason ? `why-${decision}` : undefined} onClick={onClick}>{label}</Button>
        {reason && <p id={`why-${decision}`} className="text-xs text-muted-foreground">{reason}</p>}
      </div>
    )
  }

  if (!ACTIVE.includes(detail.state)) {
    return <Section title="Review"><p className="text-sm text-muted-foreground">This case is {humanize(detail.state)}; no review action is available.</p>
      {message && <p role="status" className="mt-2 rounded-md bg-[var(--status-verified-soft)] p-2 text-sm text-[var(--status-verified-fg)]">{message}</p>}
      {audit.data && <div className="mt-3"><AuditTable compact events={[...audit.data.events].reverse().slice(0, 6)} /></div>}</Section>
  }

  return (
    <Section title="Review">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="reviewer" className="text-xs font-medium text-muted-foreground">Acting as</label>
          <NativeSelect id="reviewer" value={who.reviewer_id} onChange={(e) => setReviewerId(e.target.value)}>
            {reviewers.data?.map((r) => <option key={r.id} value={r.id}>{r.name} ({r.role}, {r.approval_limit_paise == null ? 'no limit' : `limit ₹${amount(r.approval_limit_paise)}`})</option>)}
          </NativeSelect>
        </div>

        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Proposed entries</h3>
          <Table>
            <TableHeader><TableRow><TableHead>Entry</TableHead><TableHead className="text-right">₹</TableHead></TableRow></TableHeader>
            <TableBody>
              {entries.map((e, i) => (
                <TableRow key={i}>
                  <TableCell className="text-sm">{e.kind === 'allocation' ? `Apply receipt to ${e.invoice_id}` : `Book to ${e.account}`}</TableCell>
                  <TableCell className="text-right tabular-nums">{amount(e.amount_paise)}</TableCell>
                </TableRow>
              ))}
              {!entries.length && <TableRow><TableCell colSpan={2} className="text-sm text-muted-foreground">Nothing proposed yet.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="comment" className="text-xs font-medium text-muted-foreground">Comment (required to reject or request evidence)</label>
          <Textarea id="comment" value={comment} maxLength={1000} onChange={(e) => setComment(e.target.value)} rows={2} />
        </div>

        <div className="grid gap-3">
          {action('approve', 'Approve', who.approve, 'default', () => decide('approve'))}
          {action('request_evidence', 'Request evidence', who.request_evidence, 'outline', () => decide('request_evidence'))}
          {action('reject', 'Reject', who.reject, 'destructive', () => setConfirmReject(true))}
        </div>

        <ErrorBanner error={review.error} />
        {message && <p role="status" className="rounded-md bg-[var(--status-verified-soft)] p-2 text-sm text-[var(--status-verified-fg)]">{message}</p>}

        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Audit trail for this case</h3>
          <AuditTable compact events={[...(audit.data?.events ?? [])].reverse().slice(0, 6)} />
        </div>
      </div>

      <ConfirmDialog open={confirmReject} onOpenChange={setConfirmReject} title={`Reject ${detail.case_id}?`}
        description="The case is closed as rejected and the decision is written to the audit log." confirmLabel="Reject case"
        pending={review.isPending} onConfirm={() => decide('reject')}>
        <p className="rounded bg-muted p-2 text-sm">{comment}</p>
      </ConfirmDialog>
    </Section>
  )
}
