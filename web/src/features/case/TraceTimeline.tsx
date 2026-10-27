import { useTrace } from '@/api/hooks'
import { Skeleton } from '@/components/ui/skeleton'
import { humanize } from '@/lib/format'
import { TOOL_LABEL } from '@/lib/guide'
import { ModeBadge, Section } from '@/ui/primitives'

const compact = (v: unknown) => {
  const s = JSON.stringify(v)
  return s.length > 140 ? `${s.slice(0, 140)}…` : s
}

/** The agent's run as a vertical timeline: the hypothesis it recorded and the tool it called, with a collapsed result. */
export function TraceTimeline({ caseId }: { caseId: string }) {
  const q = useTrace(caseId)
  if (q.isLoading) return <Section title="Agent trace"><Skeleton className="h-32 w-full" /></Section>
  if (!q.data) return <Section title="Agent trace"><p className="text-sm text-muted-foreground">No agent run for this case: the matcher closed it, or it has not been investigated yet.</p></Section>
  const t = q.data
  return (
    <Section title="Agent trace" aside={<div className="flex items-center gap-2 text-xs text-muted-foreground">
      {t.replay && <ModeBadge mode="replay" />}<span>{t.run.model} · {t.run.prompt_version} · stopped: {t.run.stop_reason ?? 'n/a'}</span></div>}>
      <ol className="relative ml-2 flex flex-col gap-4 border-l pl-5">
        {t.steps.map((s) => (
          <li key={s.step} className="relative">
            <span aria-hidden className="absolute -left-[1.6rem] top-1 grid size-4 place-items-center rounded-full border bg-background text-[9px] font-semibold">{s.step}</span>
            {s.hypotheses.map((h) => (
              <p key={h.id} className="text-sm"><span className="font-medium">Hypothesis · {humanize(h.kind)}</span> <span className="text-muted-foreground">({h.status})</span>: {h.text}</p>
            ))}
            {s.tool_calls.map((c) => c.tool_name === '(rejected)' ? (
              <p key={c.id} className="text-sm text-muted-foreground">Call rejected by the provider, the agent corrected it: {String((c.result_json as { error?: string }).error ?? '').slice(0, 120)}</p>
            ) : (
              <details key={c.id} className="text-sm">
                <summary className="cursor-pointer"><span className="font-medium">{TOOL_LABEL[c.tool_name] ?? humanize(c.tool_name)}</span> <span className="font-mono text-xs font-semibold">{c.tool_name}</span> <span className="font-mono text-xs text-muted-foreground">{compact(c.args_json)}</span></summary>
                <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2 text-xs">{JSON.stringify(c.result_json, null, 2)}</pre>
              </details>
            ))}
          </li>
        ))}
      </ol>
    </Section>
  )
}
