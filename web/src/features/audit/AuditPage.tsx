import { Download, RotateCcw, ShieldCheck, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AUDIT_PAGE } from '@/api/client'
import { useAudit, useReset, useTamper, useVerify } from '@/api/hooks'
import type { VerifyResult } from '@/api/types'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorBanner, Money, Section, useTitle } from '@/ui/primitives'
import { Term } from '@/ui/Term'
import { AuditTable } from './AuditTable'

export function VerifyResultBanner({ result }: { result: VerifyResult }) {
  return result.ok ? (
    <p role="status" data-testid="verify-ok" className="rounded-md bg-[var(--status-verified-soft)] p-3 text-sm font-medium text-[var(--status-verified-fg)]">
      Chain intact: {result.checked} events{result.checkpoints ? ` and ${result.checkpoints} signed checkpoint${result.checkpoints > 1 ? 's' : ''}` : ''} verified.
    </p>
  ) : (
    <p role="alert" data-testid="verify-broken" className="rounded-md bg-[var(--status-conflicting-soft)] p-3 text-sm font-medium text-[var(--status-conflicting-fg)]">
      Chain broken at event #{result.first_broken_seq}. {result.reason}
    </p>
  )
}

export function AuditPage() {
  useTitle('Audit')
  const [caseId, setCaseId] = useState('')
  const events = useAudit(caseId.trim() || undefined)
  const verify = useVerify()
  const tamper = useTamper()
  const reset = useReset()
  const broken = verify.data && !verify.data.ok ? verify.data.first_broken_seq ?? null : null
  // the event list is long and scrolls: bring the broken event into view so the break is visible, not just reported
  useEffect(() => { if (broken != null && !events.isLoading) document.getElementById(`event-${broken}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' }) }, [broken, events.isLoading, events.dataUpdatedAt])

  return (
    <div className="audit-page flex flex-col gap-6">
      <div className="page-heading">
        <div><h1>Audit ledger</h1>
        <p>Every action recorded. Every link verifiable.</p></div><span className="page-heading-note"><ShieldCheck size={15} />Hash-linked event history</span>
      </div>
      <Section title="Integrity" aside={
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => verify.mutate()} disabled={verify.isPending}><ShieldCheck /> {verify.isPending ? 'Verifying…' : 'Verify chain'}</Button>
          <a href="/api/audit/checkpoint" download className={buttonVariants({ variant: 'outline' })}><Download /> Latest signed checkpoint</a>
        </div>}>
        <p className="mb-4 max-w-2xl text-sm text-muted-foreground">Recompute the event chain and check it against the latest signed checkpoint. Verification identifies the first broken link if the history has changed.</p>
        {verify.data ? <VerifyResultBanner result={verify.data} /> : <p className="integrity-pending">Not verified yet in this session. Select Verify chain to check integrity.</p>}
        <ErrorBanner error={verify.error} className="mt-2" />
      </Section>
      <Section title="Tamper demo" aside={
        <div className="flex flex-wrap gap-2">
          <Button variant="destructive" disabled={tamper.isPending} onClick={() => tamper.mutate(undefined, { onSuccess: () => verify.mutate() })}>
            <ShieldAlert /> {tamper.isPending ? 'Editing…' : 'Simulate tampering'}</Button>
          <Button variant="outline" disabled={reset.isPending} onClick={() => reset.mutate(undefined, { onSuccess: () => verify.mutate() })}>
            <RotateCcw /> {reset.isPending ? 'Resetting…' : 'Reset environment'}</Button>
        </div>}>
        <p className="mb-3 max-w-2xl text-sm text-muted-foreground">Each event in the <Term k="ledger">ledger</Term> carries a hash of the one before it, and the database refuses edits. This button plays an insider
          with database-owner access: it edits one past event, then verifies the chain. Watch it fail at exactly that event. Resetting loads a clean environment and a fresh chain.</p>
        {tamper.data && <p role="status" className="tamper-result" data-testid="tamper-result">
          Event #{tamper.data.seq}: <code>{tamper.data.field}</code> changed from {typeof tamper.data.before === 'number' ? <Money paise={tamper.data.before} /> : String(tamper.data.before)} to {typeof tamper.data.after === 'number' ? <Money paise={tamper.data.after} /> : String(tamper.data.after)}.</p>}
        <ErrorBanner error={tamper.error ?? reset.error} className="mt-2" />
      </Section>
      <Section title="Events" aside={
        <Input aria-label="Filter by case id" placeholder="Filter by case, e.g. CASE-0007" className="h-9 w-full sm:w-64" value={caseId} onChange={(e) => setCaseId(e.target.value)} />}>
        <ErrorBanner error={events.error} />
        {!caseId.trim() && (events.data?.events.length ?? 0) >= AUDIT_PAGE && <p className="mb-3 text-xs text-muted-foreground">Showing the latest {AUDIT_PAGE} events. Filter by case to see that case’s full history.</p>}
        {events.isLoading ? <Skeleton className="h-64 w-full" /> : <AuditTable brokenSeq={broken} events={[...(events.data?.events ?? [])].reverse()} />}
      </Section>
    </div>
  )
}
