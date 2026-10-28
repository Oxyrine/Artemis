import type { CaseDetail, FlagView } from '@/api/types'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { humanize, rupees } from '@/lib/format'
import { CopyButton, Section, TierBadge } from '@/ui/primitives'

export function EvidenceList({ evidence }: { evidence: CaseDetail['evidence'] }) {
  return (
    <Section title="Evidence">
      {!evidence.length ? <p className="text-sm text-muted-foreground">No evidence was gathered: the matcher closed this case on an exact match.</p> : (
        <Table>
          <TableHeader>
            <TableRow><TableHead>ID</TableHead><TableHead>Tier</TableHead><TableHead>Kind</TableHead><TableHead>Source</TableHead>
              <TableHead>Excerpt</TableHead><TableHead>Found by</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {evidence.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="whitespace-nowrap font-mono text-xs">{e.id} <CopyButton text={e.id} label={`evidence id ${e.id}`} /></TableCell>
                <TableCell><TierBadge tier={e.tier} /></TableCell>
                <TableCell>{humanize(e.kind)}</TableCell>
                <TableCell className="font-mono text-xs">{e.source_table}:{e.source_id}</TableCell>
                <TableCell className="max-w-xs truncate text-xs" title={e.excerpt}>{e.excerpt || '—'}</TableCell>
                <TableCell className="whitespace-nowrap text-xs">{e.tool_name ? `${e.tool_name} (${e.tool_call_id})` : '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Section>
  )
}

function Side({ label, side, differs }: { label: string; side: FlagView['a']; differs: boolean }) {
  return (
    <div className="border-t py-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label} · {humanize(side.kind)}</p>
      <p className="font-mono text-xs text-muted-foreground">{side.ref}</p>
      {side.amount_paise != null && (
        <p data-testid="flag-amount" className={`mt-1 inline-block rounded px-1.5 text-xl font-semibold tabular-nums ${differs ? 'bg-[var(--status-conflicting-soft)] text-[var(--status-conflicting-fg)]' : ''}`}>
          {rupees(side.amount_paise)}
        </p>
      )}
      {side.excerpt && <p className="mt-1 text-xs">{side.excerpt}</p>}
    </div>
  )
}

/** Only for CONFLICTING cases: the two disagreeing evidence items side by side, differing values highlighted. */
export function ContradictionPanel({ flags }: { flags: FlagView[] }) {
  if (!flags.length) return null
  return (
    <Section title="Contradictions">
      <div className="flex flex-col gap-4">
        {flags.map((f, i) => {
          const differs = f.a.amount_paise != null && f.b.amount_paise != null && f.a.amount_paise !== f.b.amount_paise
          return (
            <div key={i}>
              <p className="mb-2 text-sm"><span className="font-semibold text-[var(--status-conflicting-fg)]">Flag {f.code}.</span> {f.detail}</p>
              <div className="grid gap-3 md:grid-cols-2"><Side label="A" side={f.a} differs={differs} /><Side label="B" side={f.b} differs={differs} /></div>
            </div>
          )
        })}
      </div>
    </Section>
  )
}
