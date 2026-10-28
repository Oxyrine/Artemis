import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, AUDIT_PAGE, api } from './client'
import type { AuditList, BatchStatus, CaseDetail, CaseList, Decision, EvidenceGraph, MetricsReport, Modes, ReviewResult,
  ReviewerView, RunMode, TamperResult, TraceView, VerifyResult } from './types'

export const keys = {
  cases: ['cases'] as const, case: (id: string) => ['case', id] as const, audit: (caseId?: string) => ['audit', caseId ?? 'all'] as const,
}

export const useModes = () => useQuery({ queryKey: ['modes'], queryFn: () => api<Modes>('/modes') })
export const useReviewers = () => useQuery({ queryKey: ['reviewers'], queryFn: () => api<ReviewerView[]>('/reviewers'), staleTime: Infinity })

export function useCases(filter: { status?: string; state?: string } = {}) {
  const qs = new URLSearchParams(Object.entries(filter).filter(([, v]) => v) as [string, string][]).toString()
  // empty filters are dropped from the key, so "no filter" and "filters left blank" are the same query: one request, not two
  const active = { status: filter.status || undefined, state: filter.state || undefined }
  return useQuery({ queryKey: [...keys.cases, active], queryFn: () => api<CaseList>(`/cases${qs ? `?${qs}` : ''}`), placeholderData: keepPreviousData })
}
export const useCase = (id: string) => useQuery({ queryKey: keys.case(id), queryFn: () => api<CaseDetail>(`/cases/${id}`) })
export const useGraph = (id: string) => useQuery({ queryKey: ['graph', id], queryFn: () => api<EvidenceGraph>(`/cases/${id}/graph`) })
/** `enabled` is false for a case with no agent run (the case detail says so): asking would only produce a 404 in the console. */
export const useTrace = (id: string, enabled = true) =>
  useQuery({ queryKey: ['trace', id], queryFn: () => api<TraceView>(`/cases/${id}/trace`), retry: false, enabled })
export const useMetrics = () => useQuery({ queryKey: ['metrics'], queryFn: () => api<MetricsReport>('/metrics'), retry: false })
export const useAudit = (caseId?: string) =>
  useQuery({ queryKey: keys.audit(caseId), queryFn: () => api<AuditList>(`/audit${caseId ? `?case_id=${caseId}` : `?limit=${AUDIT_PAGE}`}`) })

/** Polls once a second while the batch is running (the spec's progress bar), then refreshes everything that depends on it. */
export function useBatch(id: string | null) {
  const qc = useQueryClient()
  return useQuery({
    queryKey: ['batch', id], enabled: !!id,
    queryFn: async () => {
      const b = await api<BatchStatus>(`/batch/${id}`)
      if (!b.running) void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'batch' })
      return b
    },
    // a 404 means the server no longer has this batch (it restarted mid-run): retrying cannot bring it back
    retry: (n, err) => !(err instanceof ApiError && err.status === 404) && n < 2,
    refetchInterval: (q) => (q.state.error || (q.state.data && !q.state.data.running) ? false : 1000),
  })
}

export function useRunBatch() {
  return useMutation({ mutationFn: (mode: RunMode) => api<{ batch_id: string; mode: RunMode }>('/batch/run', { method: 'POST', json: { mode } }) })
}

export function useReset() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => api<{ cases: number; auto_closed: number }>('/reset', { method: 'POST' }),
    // batch ids restart at BATCH-0001 after a reset: drop what we know about the old ones so a new batch does not inherit their state
    onSuccess: () => { qc.removeQueries({ queryKey: ['batch'] }); return qc.invalidateQueries() } })
}

export function useTamper() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => api<TamperResult>('/demo/tamper', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['audit'] }) })
}

export function useVerify() {
  return useMutation({ mutationFn: () => api<VerifyResult>('/audit/verify') })
}

export function useReview(caseId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { reviewer: string; decision: Decision; comment: string }) =>
      api<ReviewResult>(`/cases/${caseId}/review`, { method: 'POST', reviewer: v.reviewer, json: { decision: v.decision, comment: v.comment } }),
    // the decision changes the case, the case list and the audit log: refresh them so the new event shows without a reload
    onSettled: () => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'batch' }),
  })
}
