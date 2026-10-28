import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ArrowUpRight, CircleHelp, Search, SlidersHorizontal, X, CircleCheck, CircleDashed } from 'lucide-react'
import { useCases, useMetrics } from '@/api/hooks'
import type { CaseSummary } from '@/api/types'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { STATUS_LABEL, amount, humanize, pct } from '@/lib/format'
import { NativeSelect } from '@/ui/controls'
import { ErrorBanner, Money, Section, StateBadge, StatusPill, Tile, useTitle } from '@/ui/primitives'
import { Term } from '@/ui/Term'
import { RunBar } from './RunBar'
import { Welcome, useWelcome } from './Welcome'

const STATUSES = ['AUTO_CLOSED', 'VERIFIED', 'PROBABLE', 'INSUFFICIENT', 'CONFLICTING']
const STATES = ['NEW', 'AUTO_CLOSED', 'PENDING_APPROVAL', 'AWAITING_EVIDENCE', 'NEEDS_REVIEW', 'APPLIED', 'REJECTED']

export function DashboardPage() {
  useTitle('Dashboard')
  const [status, setStatus] = useState('')
  const [state, setState] = useState('')
  const [search, setSearch] = useState('')
  const cases = useCases({ status, state })
  const d = cases.data
  const allCases = useCases()
  const totals = allCases.data
  const rows = filterCases(d?.cases ?? [], search)
  const filtered = !!(search || status || state)
  const welcome = useWelcome()
  const { hash } = useLocation()
  useEffect(() => { if (hash && !cases.isLoading) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' }) }, [hash, cases.isLoading])

  return (
    <div className="dashboard-page flex flex-col gap-6">
      <div className="page-heading">
        <div><h1>Reconciliation</h1>
        <p>Bring every receipt into balance.</p></div>
      </div>
      {welcome.hidden
        ? <button type="button" className="welcome-reopen" onClick={welcome.show}><CircleHelp size={14} />What is this, and how does it work?</button>
        : <Welcome onHide={welcome.hide} />}
      <RunBar />
      <ErrorBanner error={cases.error} />

      <div className="reconciliation-overview">
      <section className="balance-panel" aria-label="Variance overview">
        <div className="balance-panel-top"><h2>The reconciliation balance</h2></div>
        <div className="balance-total"><span>Apparent variance investigated</span><Money paise={totals?.rupees.investigated_variance_paise} /></div>
        <VarianceBridge investigated={totals?.rupees.investigated_variance_paise} explained={totals?.rupees.explained_verified_paise} held={totals?.rupees.held_paise} />
        <div className="balance-breakdown">
          <Summary label="Explained by verified cases" paise={totals?.rupees.explained_verified_paise} note="Validated evidence" icon={<CircleCheck size={15} />} />
          <Summary label="Held for evidence or review" paise={totals?.rupees.held_paise} note="Requires attention" icon={<CircleDashed size={15} />} />
        </div>
        <div className="balance-caption">Receipt differences, traced back to their source.</div>
      </section>
      <div className="outcome-section"><div className="section-intro"><h2>Investigation outcomes</h2><span>{totals?.cases.length ?? '—'} receipts</span></div>
      <div className="outcome-strip" aria-label="Cases by status" aria-busy={cases.isLoading}>
        {STATUSES.map((s) => (
          <Tile key={s} status={s} count={totals?.counts_by_status[s] ?? 0} active={status === s} onClick={() => setStatus(status === s ? '' : s)} />
        ))}
      </div><p className="outcome-caption">Select an outcome to focus your review.</p></div>
      </div>

      <Section title="Receipt queue" aside={<span className="text-xs text-muted-foreground" aria-live="polite">{cases.isLoading ? 'Loading receipts…' : `${rows.length} ${rows.length === 1 ? 'case' : 'cases'}${filtered ? ' matching filters' : ' in this workspace'}`}</span>}>
        <div className="queue-toolbar">
          <label className="queue-search"><Search size={16} aria-hidden="true" /><Input aria-label="Search receipts" placeholder="Search customer, case or UTR…" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
          <div className="queue-filters"><SlidersHorizontal size={15} aria-hidden="true" />
          <NativeSelect aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
          </NativeSelect>
          <NativeSelect aria-label="Filter by state" value={state} onChange={(e) => setState(e.target.value)}>
            <option value="">All states</option>
            {STATES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
          </NativeSelect>
          </div>
          {filtered && <Button variant="ghost" size="sm" onClick={() => { setSearch(''); setStatus(''); setState('') }}><X size={14} />Clear filters</Button>}
        </div>
        {cases.isLoading ? <Skeleton className="h-64 w-full" /> : <CaseTable rows={rows} />}
        <div className="queue-footnote"><span>Amounts in INR. Variance is subject to investigation.</span><span>Open a case to inspect evidence <ArrowUpRight size={13} /></span></div>
      </Section>

      <div id="metrics"><MetricsPanel /></div>
    </div>
  )
}

export function filterCases(rows: CaseSummary[], query: string) {
  const needle = query.trim().toLowerCase()
  return rows.filter((c) => [c.case_id, c.customer_name ?? '', ...c.utrs].some((v) => v.toLowerCase().includes(needle)))
}

const Summary = ({ label, paise, note, icon }: { label: string; paise: number | undefined; note: string; icon: ReactNode }) => (
  <div className="financial-summary-cell">
    <p>{icon}{label}</p>
    <strong><Money paise={paise ?? null} /></strong>
    <span>{note}</span>
  </div>
)

export function VarianceBridge({ investigated, explained, held }: { investigated?: number; explained?: number; held?: number }) {
  const total = (explained ?? 0) + (held ?? 0)
  const share = total > 0 ? (explained ?? 0) / total : 0
  return <div className="variance-bridge" role="img" aria-label={investigated == null ? 'Variance data unavailable' : total > 0 ? `${Math.round(share * 100)}% of reported variance explained; ${100 - Math.round(share * 100)}% held for evidence or review` : 'No variance investigated yet'}>
    <div className="bridge-labels"><span>Explained</span><span>Held for review</span></div>
    <div className={`bridge-track ${total === 0 ? 'bridge-empty' : ''}`}><span className="bridge-explained" style={{ width: `${share * 100}%` }} /><span className="bridge-held" style={{ width: `${(1 - share) * 100}%` }} /></div>
  </div>
}

function CaseTable({ rows }: { rows: CaseSummary[] }) {
  if (!rows.length) return <div className="queue-empty"><Search size={24} strokeWidth={1.5} /><h3>No receipts found</h3><p>Clear your search or filters to return to the receipt queue.</p></div>
  return (
    <><div className="desktop-case-list"><Table>
      <TableHeader>
        <TableRow>
          <TableHead>Customer / <Term k="utr">receipt</Term></TableHead><TableHead>Case</TableHead>
          <TableHead className="text-right">Receipt ₹</TableHead><TableHead className="text-right"><Term k="variance" /> ₹</TableHead>
          <TableHead>Outcome</TableHead><TableHead>Review state</TableHead><TableHead><span className="sr-only">Open case</span></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((c) => (
          <TableRow key={c.case_id}>
            <TableCell><Link to={`/cases/${c.case_id}`} className="customer-link">{c.customer_name ?? 'Unresolved customer'}<span>{c.utrs[0]}{c.utrs.length > 1 ? ` +${c.utrs.length - 1}` : ''}</span></Link></TableCell>
            <TableCell><Link to={`/cases/${c.case_id}`} className="case-id-link">{c.case_id}</Link></TableCell>
            <TableCell className="text-right tabular-nums">{amount(c.receipt_paise)}</TableCell>
            <TableCell className="text-right tabular-nums">{c.variance_paise == null ? '—' : amount(c.variance_paise)}</TableCell>
            <TableCell><StatusPill status={c.status} /></TableCell>
            <TableCell><StateBadge state={c.state} /></TableCell>
            <TableCell><Link to={`/cases/${c.case_id}`} aria-label={`Review ${c.case_id}`} className="row-open"><ArrowUpRight size={16} /></Link></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table></div>
    <div className="mobile-case-list">
      {rows.map((c) => <article key={c.case_id} className="mobile-case-row">
        <div className="mobile-case-top"><Link to={`/cases/${c.case_id}`} className="customer-link">{c.customer_name ?? 'Unresolved customer'}<span>{c.case_id} · {c.utrs.join(' + ')}</span></Link><Link to={`/cases/${c.case_id}`} className="row-open" aria-label={`Review ${c.case_id}`}><ArrowUpRight size={17} /></Link></div>
        <dl className="mobile-case-amounts"><div><dt>Receipt</dt><dd><Money paise={c.receipt_paise} /></dd></div><div><dt>Variance</dt><dd><Money paise={c.variance_paise} /></dd></div></dl>
        <div className="mobile-case-state"><StatusPill status={c.status} /><StateBadge state={c.state} /></div>
      </article>)}
    </div></>
  )
}

function MetricsPanel() {
  const m = useMetrics()
  if (m.isLoading) return <Skeleton className="h-28 w-full" />
  if (!m.data || m.data.runs === 0) return <Section title="Evaluation metrics"><p className="text-sm text-muted-foreground">Run a batch to see precision, abstention accuracy and tool-path diversity.</p></Section>
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
