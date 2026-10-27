import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { AuditList, BatchStatus, CaseDetail, CaseList, Decision, EvidenceGraph, MetricsReport, Modes, ReviewResult,
  ReviewerView, RunMode, TamperResult, TraceView, VerifyResult } from './types'

export const keys = {
  cases: ['cases'] as const, case: (id: string) => ['case', id] as const, audit: (caseId?: string) => ['audit', caseId ?? 'all'] as const,
}

export const useModes = () => useQuery({ queryKey: ['modes'], queryFn: () => api<Modes>('/modes') })
export const useReviewers = () => useQuery({ queryKey: ['reviewers'], queryFn: () => api<ReviewerView[]>('/reviewers'), staleTime: Infinity })

export function useCases(filter: { status?: string; state?: string } = {}) {
  const qs = new URLSearchParams(Object.entries(filter).filter(([, v]) => v) as [string, string][]).toString()
  return useQuery({ queryKey: [...keys.cases, filter], queryFn: () => api<CaseList>(`/cases${qs ? `?${qs}` : ''}`), placeholderData: keepPreviousData })
}
export const useCase = (id: string) => useQuery({ queryKey: keys.case(id), queryFn: () => api<CaseDetail>(`/cases/${id}`) })
export const useGraph = (id: string) => useQuery({ queryKey: ['graph', id], queryFn: () => api<EvidenceGraph>(`/cases/${id}/graph`) })
export const useTrace = (id: string) => useQuery({ queryKey: ['trace', id], queryFn: () => api<TraceView>(`/cases/${id}/trace`), retry: false })
export const useMetrics = () => useQuery({ queryKey: ['metrics'], queryFn: () => api<MetricsReport>('/metrics'), retry: false })
export const useAudit = (caseId?: string) =>
  useQuery({ queryKey: keys.audit(caseId), queryFn: () => api<AuditList>(`/audit${caseId ? `?case_id=${caseId}` : ''}`) })

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
    refetchInterval: (q) => (q.state.data && !q.state.data.running ? false : 1000),
  })
}

export function useRunBatch() {
  return useMutation({ mutationFn: (mode: RunMode) => api<{ batch_id: string; mode: RunMode }>('/batch/run', { method: 'POST', json: { mode } }) })
}

export function useReset() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => api<{ cases: number; auto_closed: number }>('/reset', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries() })
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
