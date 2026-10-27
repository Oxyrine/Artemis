import { Play, RotateCcw, Workflow } from 'lucide-react'
import { useState } from 'react'
import { useModes } from '@/api/hooks'
import type { RunMode } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ConfirmDialog, NativeSelect } from '@/ui/controls'
import { ErrorBanner, ModeBadge } from '@/ui/primitives'
import { useBatchRunner } from './BatchProvider'

/** "Run batch" with the agent mode switch, a progress bar fed by polling, and a demo-only reset. */
export function RunBar() {
  const modes = useModes()
  const [mode, setMode] = useState<RunMode>('demo')
  const [confirmReset, setConfirmReset] = useState(false)
  const runner = useBatchRunner()
  // nothing NEW means the server would answer 409: say so instead of offering a button that can only fail
  const { running, nothingNew } = runner
  const b = runner.status
  const pct = b && b.total ? Math.round((100 * b.done) / b.total) : 0
  const chosen = modes.data?.modes.find((m) => m.mode === mode)
  const allDone = nothingNew && mode !== 'replay'

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
        <Button id="run-batch" disabled={running || allDone || chosen?.available === false}
          onClick={() => runner.run(mode)}>
          <Play /> {running ? 'Running…' : 'Run batch'}
        </Button>
        <Button variant="ghost" size="icon" title="Reset environment" aria-label="Reset environment" disabled={running} onClick={() => setConfirmReset(true)}><RotateCcw /></Button>
        {b && <ModeBadge mode={b.mode} />}
      </div>

      {runner.lost && <p role="status" className="text-sm text-[var(--status-probable-fg)]">The server restarted while the batch was running, so its progress was lost. Run the batch again to continue with the cases that are still waiting.</p>}
      {allDone && !running && <p className="text-sm text-muted-foreground">Every case has already been investigated. Reset the environment to run the batch again.</p>}
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
      <ErrorBanner error={runner.runError ?? runner.resetError} />
      {b && Object.keys(b.errors).length > 0 && (
        <ErrorBanner error={new Error(`${Object.keys(b.errors).length} case(s) failed and were sent to review: ${Object.values(b.errors)[0]}`)} />
      )}

      <ConfirmDialog open={confirmReset} onOpenChange={setConfirmReset} title="Reset the environment?"
        description="This reloads the 40-case seed data and clears every decision, run and audit event. It is a demo-only action."
        confirmLabel="Reset" pending={runner.resetPending}
        onConfirm={() => runner.reset(() => setConfirmReset(false))} />
    </div>
  )
}
