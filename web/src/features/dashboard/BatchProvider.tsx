import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useBatch, useCases, useReset, useRunBatch } from '@/api/hooks'
import type { BatchStatus, RunMode } from '@/api/types'

type Runner = {
  status: BatchStatus | undefined
  running: boolean
  /** the server forgot the batch we were following (it restarted mid-run); its progress is gone */
  lost: boolean
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
  const qc = useQueryClient()
  const [lost, setLost] = useState(false)
  // true from the moment we start a batch until we have seen it finish: only then is a vanished batch "lost" work
  const following = useRef(false)
  if (batch.data && !batch.data.running) following.current = false
  useEffect(() => {
    if (!batch.error) return
    if (following.current) setLost(true) // a stale error for a finished or reset batch is not news
    following.current = false
    setBatchId(null)
  }, [batch.error])

  const running = runM.isPending || !!batch.data?.running
  const nothingNew = !!cases.data?.cases.length && cases.data.cases.every((c) => c.state !== 'NEW')

  const startRun = useCallback((mode: RunMode) => {
    setLost(false)
    runM.mutate(mode, { onSuccess: (d) => { qc.removeQueries({ queryKey: ['batch'] }); following.current = true; setBatchId(d.batch_id) } })
  }, [runM, qc])
  const run = startRun
  // clear the batch first: the old id no longer exists once the server resets, and its "Done" text would mislead meanwhile
  const reset = useCallback((onDone?: () => void) => {
    setBatchId(null)
    setLost(false)
    following.current = false
    resetM.mutate(undefined, { onSuccess: () => onDone?.() })
  }, [resetM])
  const resetAndRun = useCallback((mode: RunMode) => {
    setBatchId(null)
    setLost(false)
    following.current = false
    resetM.mutate(undefined, { onSuccess: () => startRun(mode) })
  }, [resetM, startRun])

  const value = useMemo<Runner>(() => ({
    status: batch.data, running: running || resetM.isPending, lost, nothingNew, run, reset, resetAndRun,
    runError: runM.error, resetError: resetM.error, resetPending: resetM.isPending,
  }), [batch.data, running, lost, resetM.isPending, resetM.error, runM.error, nothingNew, run, reset, resetAndRun])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useBatchRunner(): Runner {
  const r = useContext(Ctx)
  if (!r) throw new Error('useBatchRunner must be used inside BatchProvider')
  return r
}
