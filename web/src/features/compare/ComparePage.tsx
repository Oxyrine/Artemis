import { ArrowRight, GitCompareArrows } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useCase, useTrace } from '@/api/hooks'
import type { CaseDetail, TraceView } from '@/api/types'
import { buttonVariants } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { distinctPaths, hypothesisLog, markPaths, notCalled, taxFacts } from '@/lib/compare'
import { rupees, humanize } from '@/lib/format'
import { GRADE_NOTE, SHOWCASE, TOOL_LABEL } from '@/lib/guide'
import { Money, Section, StateBadge, StatusPill, useTitle } from '@/ui/primitives'
import { Term } from '@/ui/Term'

/** The hero case and its two twins, side by side: same shape of problem, different evidence, different tool path. */
export function ComparePage() {
  useTitle('Agent paths')
  const traces = [useTrace(SHOWCASE[0].caseId), useTrace(SHOWCASE[1].caseId), useTrace(SHOWCASE[2].caseId)]
  const cases = [useCase(SHOWCASE[0].caseId), useCase(SHOWCASE[1].caseId), useCase(SHOWCASE[2].caseId)]
  const loading = traces.some((t) => t.isLoading)
  const ready = traces.every((t) => !!t.data)
  const paths = ready ? traces.map((t) => (t.data as TraceView).tool_path) : []
  const chips = ready ? markPaths(paths) : []
  const missing = ready ? notCalled(paths) : []

  return (
    <div className="compare-page flex flex-col gap-6">
      <div className="page-heading">
        <div><h1>Agent paths</h1><p>The same kind of problem, three different pieces of evidence, three different investigations.</p></div>
        <span className="page-heading-note"><GitCompareArrows size={15} />Hero case and twins</span>
      </div>

      {loading && <Skeleton className="h-96 w-full" />}
      {!loading && !ready && (
        <Section title="Run the batch first">
          <p className="mb-4 max-w-2xl text-sm text-muted-foreground">The comparison reads each case’s recorded agent run, so it appears once the batch has investigated the exceptions.</p>
          <Link to="/" className={buttonVariants()}>Go to the dashboard<ArrowRight size={14} /></Link>
        </Section>
      )}
      {ready && (
        <>
          <p className="compare-summary" role="status">
            <strong>{distinctPaths(paths)} cases, {distinctPaths(paths)} different tool sequences.</strong> The agent was never told what to do for each case:
            what it found at the tax-credit extract decided whether it finished, revised its hypothesis, or asked for more evidence.
          </p>
          <div className="compare-grid">
            {SHOWCASE.map((s, i) => (
              <CompareColumn key={s.caseId} role={s.role} lead={s.lead} caseId={s.caseId} trace={traces[i].data as TraceView}
                detail={cases[i].data} chips={chips[i]} missing={missing[i]} />
            ))}
          </div>
          <p className="compare-note">Highlighted steps happen only in some of the three runs. Every number in each run comes from a tool; the agent never calculates money.</p>
        </>
      )}
    </div>
  )
}

function CompareColumn({ role, lead, caseId, trace, detail, chips, missing }: {
  role: string; lead: string; caseId: string; trace: TraceView; detail: CaseDetail | undefined
  chips: { tool: string; distinctive: boolean }[]; missing: string[]
}) {
  const tax = taxFacts(trace)
  const hyp = hypothesisLog(trace)
  const note = detail?.status ? GRADE_NOTE[detail.status] : undefined
  return (
    <article className="compare-col" data-status={detail?.status ?? 'NONE'}>
      <header>
        <p className="compare-role">{role}</p>
        <h2><Link to={`/cases/${caseId}`}>{caseId}</Link></h2>
        <p className="compare-lead">{lead}</p>
        <div className="compare-badges"><StatusPill status={detail?.status} />{detail && <StateBadge state={detail.state} />}</div>
      </header>

      <dl className="compare-facts">
        <div><dt>Expected <Term k="tds">TDS</Term> (rule engine)</dt><dd><Money paise={tax.computed_paise} /></dd></div>
        <div><dt>Tax-credit extract returned</dt>
          <dd>{tax.rows.length === 0 ? <span className="fact-none">Nothing filed</span> : tax.rows.map((r, i) => <span key={i}>{rupees(r.amount_paise)}</span>)}</dd></div>
        {detail && <div><dt>Do the sources agree?</dt>
          <dd className={detail.grade.flags.length ? 'fact-bad' : 'fact-good'}>{detail.grade.flags.length ? `No: ${detail.grade.flags.length} contradiction${detail.grade.flags.length > 1 ? 's' : ''}` : 'Yes'}</dd></div>}
      </dl>

      <h3>Tool path <span>{trace.tool_path.length} calls</span></h3>
      <ol className="path-chips">
        {chips.map((c, i) => (
          <li key={i} data-distinctive={c.distinctive} title={c.tool}>
            <span className="chip-n">{i + 1}</span>{TOOL_LABEL[c.tool] ?? humanize(c.tool)}
          </li>
        ))}
      </ol>
      {missing.length > 0 && <p className="compare-missing"><strong>Not called here:</strong> {missing.map((t) => TOOL_LABEL[t] ?? humanize(t)).join(' · ')}</p>}

      <h3>What the agent believed</h3>
      <ul className="hyp-log">
        {hyp.map((h, i) => <li key={i}><span data-h={h.status}>{humanize(h.status)}</span>{h.text}</li>)}
      </ul>

      {note && <div className="compare-grade"><strong>{note.title}</strong><span>{note.text}</span></div>}
      <Link to={`/cases/${caseId}`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>Open the full case<ArrowRight size={14} /></Link>
    </article>
  )
}
