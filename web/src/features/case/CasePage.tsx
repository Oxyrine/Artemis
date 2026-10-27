import { lazy, Suspense } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useCase } from '@/api/hooks'
import { ApiError } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { amount, dateTime } from '@/lib/format'
import { CopyButton, ErrorBanner, ModeBadge, Money, Section, StateBadge, StatusPill, useTitle } from '@/ui/primitives'
import { ClosureCard } from './ClosureCard'
import { ContradictionPanel, EvidenceList } from './EvidencePanels'
import { GRADE_NOTE } from '@/lib/guide'
import { ReviewerPanel } from './ReviewerPanel'
import { TraceTimeline } from './TraceTimeline'

// React Flow and dagre are the heaviest dependencies: load them only when a case is opened
const EvidenceGraphView = lazy(() => import('./EvidenceGraphView').then((m) => ({ default: m.EvidenceGraphView })))

export function CasePage() {
  const { caseId = '' } = useParams()
  useTitle(caseId)
  const q = useCase(caseId)
  const d = q.data

  if (q.isLoading) return <div className="flex flex-col gap-4"><Skeleton className="h-16 w-full" /><Skeleton className="h-64 w-full" /></div>
  if (!d) {
    const missing = q.error instanceof ApiError && q.error.status === 404
    return <div className="flex flex-col gap-3"><ErrorBanner error={missing ? new Error(`There is no case ${caseId}.`) : q.error} />
      <Link to="/" className="text-sm underline">Back to the dashboard</Link></div>
  }
  const total = d.receipts.reduce((s, r) => s + r.amount_paise, 0)
  const score = d.receipts[0]?.resolution_score

  return (
    <div className="flex flex-col gap-6">
      <div className="case-heading">
        <Link to="/" className="back-link"><ArrowLeft size={14} />Receipt queue</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{d.customer_name ?? d.case_id}</h1><span className="case-id-link">{d.customer_name ? d.case_id : ''}</span>
          <StatusPill status={d.status} /><StateBadge state={d.state} />
          {d.run && <ModeBadge mode={d.run.replay ? 'replay' : d.run.model === 'scripted' ? 'demo' : 'live'} />}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {d.receipts.map((r, i) => <span key={r.utr}>{i > 0 && ' + '}<span className="font-mono">{r.utr}</span> <CopyButton text={r.utr} label={`UTR ${r.utr}`} /></span>)}
          {' · '}{d.customer_name ?? 'customer not resolved'}
          {score != null && score < 100 && <> <span title="Matched by name similarity, not by GSTIN or PAN">(alias match, score {score})</span></>}
          {' · '}<Money paise={total} />
        </p>
      </div>

      <div className="case-workspace">
        <div className="case-main flex min-w-0 flex-col gap-6">
          {d.status && GRADE_NOTE[d.status] && <div className="grade-note" data-status={d.status}><strong>{GRADE_NOTE[d.status].title}</strong><span>{GRADE_NOTE[d.status].text}</span></div>}
          {d.narrative && (
            <Section title="Investigation summary" aside={d.narrative_source === 'template' ? <Badge variant="outline" title="Built from engine outputs. An LLM rewrite is only used when every figure and id checks out.">Template</Badge> : <Badge variant="secondary">Rephrased by the model</Badge>}>
              <p className="text-sm leading-relaxed">{d.narrative}</p>
            </Section>
          )}
          {d.closure && <ClosureCard closure={d.closure} />}
          {d.grade.duplicate && <Section title="Duplicate payment"><p className="text-sm">{d.grade.recommendation}</p></Section>}
          <ContradictionPanel flags={d.grade.flags} />
          {d.allocations.length > 0 && <Suspense fallback={<Skeleton className="h-72 w-full" />}><EvidenceGraphView caseId={d.case_id} /></Suspense>}
          <ReceiptsAndInvoices d={d} />
          <EvidenceList evidence={d.evidence} />
          <TraceTimeline caseId={d.case_id} />
        </div>
        <aside className="lg:sticky lg:top-20 lg:self-start"><ReviewerPanel detail={d} /></aside>
      </div>
    </div>
  )
}

function ReceiptsAndInvoices({ d }: { d: NonNullable<ReturnType<typeof useCase>['data']> }) {
  return (
    <Section title="Receipt and invoices">
      <Table>
        <TableHeader><TableRow><TableHead>Item</TableHead><TableHead>Detail</TableHead><TableHead className="text-right">₹</TableHead></TableRow></TableHeader>
        <TableBody>
          {d.receipts.map((r) => (
            <TableRow key={r.utr}><TableCell className="font-mono text-xs">{r.utr}</TableCell>
              <TableCell className="text-xs">{dateTime(r.value_date)} · {r.narration}{r.bank_charges_paise ? ` · bank charges ₹${amount(r.bank_charges_paise)}` : ''}</TableCell>
              <TableCell className="text-right tabular-nums">{amount(r.amount_paise)}</TableCell></TableRow>
          ))}
          {d.invoices.map((i) => (
            <TableRow key={i.id}><TableCell className="font-mono text-xs">{i.id}</TableCell>
              <TableCell className="text-xs">due {i.due_date} · taxable ₹{amount(i.taxable_paise)} + GST ₹{amount(i.gst_paise)} · {i.status}</TableCell>
              <TableCell className="text-right tabular-nums">{amount(i.gross_paise)}</TableCell></TableRow>
          ))}
        </TableBody>
      </Table>
    </Section>
  )
}
