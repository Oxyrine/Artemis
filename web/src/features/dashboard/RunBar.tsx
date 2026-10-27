import { Play, RotateCcw, Workflow } from 'lucide-react'
import { useState } from 'react'
import { useBatch, useModes, useReset, useRunBatch } from '@/api/hooks'
import type { RunMode } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ConfirmDialog, NativeSelect } from '@/ui/controls'
import { ErrorBanner, ModeBadge } from '@/ui/primitives'

/** "Run batch" with the agent mode switch, a progress bar fed by polling, and a demo-only reset. */
export function RunBar() {
  const modes = useModes()
  const [mode, setMode] = useState<RunMode>('demo')
  const [batchId, setBatchId] = useState<string | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)
  const run = useRunBatch()
  const reset = useReset()
  const batch = useBatch(batchId)

  const running = run.isPending || !!batch.data?.running
  const b = batch.data
  const pct = b && b.total ? Math.round((100 * b.done) / b.total) : 0
  const chosen = modes.data?.modes.find((m) => m.mode === mode)

  return (
    <div className="agent-toolbar">
      <div className="agent-toolbar-row">
        <div className="agent-description"><Workflow size={20} strokeWidth={1.5} /><div><strong>Investigation agent</strong><span>Gather evidence. Explain the difference.</span></div></div>
        <div className="flex flex-col gap-1">
          <label htmlFor="mode" className="sr-only">Agent mode</label>
          <NativeSelect id="mode" value={mode} disabled={running} onChange={(e) => setMode(e.target.value as RunMode)}>
            {modes.data?.modes.map((m) => (
              <option key={m.mode} value={m.mode} disabled={!m.available}>{m.label}{m.available ? '' : ' (unavailable)'}</option>
            )) ?? <option value="demo">Demo agent</option>}
          </NativeSelect>
        </div>
        <Button id="run-batch" disabled={running || chosen?.available === false}
          onClick={() => run.mutate(mode, { onSuccess: (d) => setBatchId(d.batch_id) })}>
          <Play /> {running ? 'Running…' : 'Run batch'}
        </Button>
        <Button variant="ghost" size="icon" title="Reset environment" aria-label="Reset environment" disabled={running} onClick={() => setConfirmReset(true)}><RotateCcw /></Button>
        {b && <ModeBadge mode={b.mode} />}
      </div>

      {chosen && !chosen.available && <p className="text-sm text-muted-foreground">{chosen.reason}</p>}
      {b && (
        <div className="flex flex-col gap-1" role="status" aria-live="polite">
          <Progress value={pct} aria-label="Batch progress" />
          <p className="text-xs text-muted-foreground">
            {b.running ? `Investigating ${b.done} of ${b.total} cases…` : `Finished: ${b.done} of ${b.total} investigated`}
            {b.replay ? ' · replayed from a recording, no LLM calls' : ''}
          </p>
        </div>
      )}
      <ErrorBanner error={run.error ?? reset.error} />
      {b && Object.keys(b.errors).length > 0 && (
        <ErrorBanner error={new Error(`${Object.keys(b.errors).length} case(s) failed and were sent to review: ${Object.values(b.errors)[0]}`)} />
      )}

      <ConfirmDialog open={confirmReset} onOpenChange={setConfirmReset} title="Reset the environment?"
        description="This reloads the 40-case seed data and clears every decision, run and audit event. It is a demo-only action."
        confirmLabel="Reset" pending={reset.isPending}
        onConfirm={() => reset.mutate(undefined, { onSuccess: () => { setConfirmReset(false); setBatchId(null) } })} />
    </div>
  )
}
