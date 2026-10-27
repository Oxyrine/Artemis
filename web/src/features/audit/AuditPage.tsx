import { Download, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useAudit, useVerify } from '@/api/hooks'
import type { VerifyResult } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorBanner, Section, useTitle } from '@/ui/primitives'
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

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
        <p className="text-sm text-muted-foreground">Every step is a hash-linked event. Verify recomputes the chain and checks it against the latest signed checkpoint.</p>
      </div>
      <Section title="Integrity" aside={
        <div className="flex gap-2">
          <Button onClick={() => verify.mutate()} disabled={verify.isPending}><ShieldCheck /> {verify.isPending ? 'Verifying…' : 'Verify chain'}</Button>
          <Button variant="outline" render={<a href="/api/audit/checkpoint" download />}><Download /> Latest signed checkpoint</Button>
        </div>}>
        {verify.data ? <VerifyResultBanner result={verify.data} /> : <p className="text-sm text-muted-foreground">Not verified yet in this session.</p>}
        <ErrorBanner error={verify.error} className="mt-2" />
      </Section>
      <Section title="Events" aside={
        <Input aria-label="Filter by case id" placeholder="Filter by case, e.g. CASE-0007" className="h-9 w-64" value={caseId} onChange={(e) => setCaseId(e.target.value)} />}>
        <ErrorBanner error={events.error} />
        {events.isLoading ? <Skeleton className="h-64 w-full" /> : <AuditTable events={[...(events.data?.events ?? [])].reverse()} />}
      </Section>
    </div>
  )
}
