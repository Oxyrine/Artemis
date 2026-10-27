import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { useBatch, useCases, useReset, useRunBatch } from '@/api/hooks'
import type { BatchStatus, RunMode } from '@/api/types'

type Runner = {
  status: BatchStatus | undefined
  running: boolean
  /** every case has left NEW: the server would answer 409, so callers should reset first */
  nothingNew: boolean
  run: (mode: RunMode) => void
  reset: (onDone?: () => void) => void
  /** reset to the seed state, then run: what "run the demo" means when the demo has already been run */
  resetAndRun: (mode: RunMode) => void
  runError: unknown
  resetError: unknown
  resetPending: boolean
}
const Ctx = createContext<Runner | null>(null)

/** One place owns "which batch is running", so the Run batch button and the guided demo drive the same one. */
export function BatchProvider({ children }: { children: ReactNode }) {
  const [batchId, setBatchId] = useState<string | null>(null)
  const runM = useRunBatch()
  const resetM = useReset()
  const batch = useBatch(batchId)
  const cases = useCases()

  const running = runM.isPending || !!batch.data?.running
  const nothingNew = !!cases.data?.cases.length && cases.data.cases.every((c) => c.state !== 'NEW')

  const run = useCallback((mode: RunMode) => runM.mutate(mode, { onSuccess: (d) => setBatchId(d.batch_id) }), [runM])
  // clear the batch first: the old id no longer exists once the server resets, and its "Done" text would mislead meanwhile
  const reset = useCallback((onDone?: () => void) => {
    setBatchId(null)
    resetM.mutate(undefined, { onSuccess: () => onDone?.() })
  }, [resetM])
  const resetAndRun = useCallback((mode: RunMode) => {
    setBatchId(null)
    resetM.mutate(undefined, { onSuccess: () => runM.mutate(mode, { onSuccess: (d) => setBatchId(d.batch_id) }) })
  }, [resetM, runM])

  const value = useMemo<Runner>(() => ({
    status: batch.data, running: running || resetM.isPending, nothingNew, run, reset, resetAndRun,
    runError: runM.error, resetError: resetM.error, resetPending: resetM.isPending,
  }), [batch.data, running, resetM.isPending, resetM.error, runM.error, nothingNew, run, reset, resetAndRun])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useBatchRunner(): Runner {
  const r = useContext(Ctx)
  if (!r) throw new Error('useBatchRunner must be used inside BatchProvider')
  return r
}
