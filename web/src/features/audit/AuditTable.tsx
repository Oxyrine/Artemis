import type { AuditEvent } from '@/api/types'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { dateTime, humanize, shortHash } from '@/lib/format'
import { CopyButton } from '@/ui/primitives'

/** Global or per-case event list: seq, time, actor, type, short hash (the full hash is one click away). */
export function AuditTable({ events, compact = false, brokenSeq = null }: { events: AuditEvent[]; compact?: boolean; brokenSeq?: number | null }) {
  if (!events.length) return <p className="py-6 text-center text-sm text-muted-foreground">No audit events yet. Run a batch.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow><TableHead className="w-14">Seq</TableHead>{!compact && <TableHead>Time</TableHead>}<TableHead>Actor</TableHead>
          <TableHead>Event</TableHead>{!compact && <TableHead>Case</TableHead>}<TableHead>Hash</TableHead></TableRow>
      </TableHeader>
      <TableBody>
        {events.map((e) => (
          <TableRow key={e.seq} id={`event-${e.seq}`} data-broken={e.seq === brokenSeq || undefined} className={e.seq === brokenSeq ? 'row-broken' : undefined}>
            <TableCell className="tabular-nums">{e.seq}</TableCell>
            {!compact && <TableCell className="whitespace-nowrap text-xs">{dateTime(e.created_at)}</TableCell>}
            <TableCell className="text-xs">{e.actor}</TableCell>
            <TableCell className="text-sm">{humanize(e.event_type)}</TableCell>
            {!compact && <TableCell className="text-xs">{e.case_id ?? '—'}</TableCell>}
            <TableCell className="whitespace-nowrap font-mono text-xs" title={e.hash}>{shortHash(e.hash)} <CopyButton text={e.hash} label={`hash of event ${e.seq}`} /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
