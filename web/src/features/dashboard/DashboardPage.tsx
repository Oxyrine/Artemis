import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCases, useMetrics } from '@/api/hooks'
import type { CaseSummary } from '@/api/types'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { STATUS_LABEL, amount, pct } from '@/lib/format'
import { NativeSelect } from '@/ui/controls'
import { ErrorBanner, Money, Section, StateBadge, StatusPill, Tile, useTitle } from '@/ui/primitives'
import { RunBar } from './RunBar'

const STATUSES = ['AUTO_CLOSED', 'VERIFIED', 'PROBABLE', 'INSUFFICIENT', 'CONFLICTING']
const STATES = ['NEW', 'AUTO_CLOSED', 'PENDING_APPROVAL', 'AWAITING_EVIDENCE', 'NEEDS_REVIEW', 'APPLIED', 'REJECTED']

export function DashboardPage() {
  useTitle('Dashboard')
  const [status, setStatus] = useState('')
  const [state, setState] = useState('')
  const cases = useCases({ status, state })
  const d = cases.data

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Receipts to reconcile</h1>
        <p className="text-sm text-muted-foreground">Run the batch, then open any case to see the evidence and decide.</p>
      </div>
      <RunBar />
      <ErrorBanner error={cases.error} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5" aria-label="Cases by status">
        {STATUSES.map((s) => (
          <Tile key={s} status={s} count={d?.counts_by_status[s] ?? 0} active={status === s} onClick={() => setStatus(status === s ? '' : s)} />
        ))}
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Summary label="Apparent variance investigated" paise={d?.rupees.investigated_variance_paise} />
        <Summary label="Explained by Verified cases" paise={d?.rupees.explained_verified_paise} />
        <Summary label="Held for evidence or review" paise={d?.rupees.held_paise} />
      </div>

      <Section title="Cases" aside={
        <div className="flex gap-2">
          <NativeSelect aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
          </NativeSelect>
          <NativeSelect aria-label="Filter by state" value={state} onChange={(e) => setState(e.target.value)}>
            <option value="">All states</option>
            {STATES.map((s) => <option key={s} value={s}>{s.replace(/_/g, ' ').toLowerCase()}</option>)}
          </NativeSelect>
        </div>}>
        {cases.isLoading ? <Skeleton className="h-64 w-full" /> : <CaseTable rows={d?.cases ?? []} />}
      </Section>

      <MetricsPanel />
    </div>
  )
}

const Summary = ({ label, paise }: { label: string; paise: number | undefined }) => (
  <div className="rounded-lg border bg-card p-4">
    <p className="text-sm text-muted-foreground">{label}</p>
    <p className="mt-1 text-2xl font-semibold"><Money paise={paise ?? null} /></p>
  </div>
)

function CaseTable({ rows }: { rows: CaseSummary[] }) {
  if (!rows.length) return <p className="py-8 text-center text-sm text-muted-foreground">No cases match. Clear a filter, or reset the environment.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Case</TableHead><TableHead>UTR</TableHead><TableHead>Customer</TableHead>
          <TableHead className="text-right">Receipt</TableHead><TableHead className="text-right">Variance</TableHead>
          <TableHead>Status</TableHead><TableHead>State</TableHead><TableHead className="text-right">Steps</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((c) => (
          <TableRow key={c.case_id}>
            <TableCell><Link to={`/cases/${c.case_id}`} className="font-medium underline-offset-2 hover:underline">{c.case_id}</Link></TableCell>
            <TableCell className="tabular-nums">{c.utrs[0]}{c.utrs.length > 1 ? ` +${c.utrs.length - 1}` : ''}</TableCell>
            <TableCell>{c.customer_name ?? <span className="text-muted-foreground">unresolved</span>}</TableCell>
            <TableCell className="text-right tabular-nums">{amount(c.receipt_paise)}</TableCell>
            <TableCell className="text-right tabular-nums">{c.variance_paise == null ? '—' : amount(c.variance_paise)}</TableCell>
            <TableCell><StatusPill status={c.status} /></TableCell>
            <TableCell><StateBadge state={c.state} /></TableCell>
            <TableCell className="text-right tabular-nums">{c.steps ?? '—'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function MetricsPanel() {
  const m = useMetrics()
  if (m.isLoading) return <Skeleton className="h-28 w-full" />
  if (!m.data) return <Section title="Evaluation metrics"><p className="text-sm text-muted-foreground">Run a batch to see precision, abstention accuracy and tool-path diversity.</p></Section>
  const x = m.data
  const cells: [string, string, string?][] = [
    ['Verified precision', pct(x.verified_precision), 'Cases graded Verified whose answer key is Verified. 100% means zero false clears.'],
    ['Abstention accuracy', pct(x.abstention_accuracy), 'Red-team and ambiguous cases left out of Applied.'],
    ['Evidence coverage', pct(x.evidence_coverage), 'Verified cases whose every adjustment cites evidence.'],
    ['Status accuracy', pct(x.status_accuracy)],
    ['Autonomous completion', pct(x.autonomous_completion), 'Exceptions that finished within bounds with no human input.'],
    ['Tool-path diversity', String(x.tool_path_diversity), 'Distinct tool sequences: the agent adapts to the evidence.'],
    ['Mean steps', x.mean_steps.toFixed(1)],
    ['Mean tokens', Math.round(x.mean_tokens).toLocaleString('en-IN')],
  ]
  return (
    <Section title="Evaluation metrics" aside={<span className="text-xs text-muted-foreground">{x.cases} cases · synthetic benchmark, not real-world accuracy</span>}>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-4">
        {cells.map(([k, v, hint]) => (
          <div key={k} title={hint}><dt className="text-xs text-muted-foreground">{k}</dt><dd className="text-xl font-semibold tabular-nums">{v}</dd></div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-muted-foreground">
        False clears: {x.false_clears.length || 'none'} · Red-team cases applied: {x.red_team_applied.length || 'none'}
      </p>
    </Section>
  )
}
