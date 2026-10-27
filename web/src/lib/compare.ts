// Pure helpers for the "agent paths" comparison: no React, no fetching, so they are cheap to test.
import type { TraceView } from '@/api/types'

export type PathChip = { tool: string; distinctive: boolean }

/** The k-th call of a tool is "distinctive" when not every path calls that tool at least k times. */
export function markPaths(paths: string[][]): PathChip[][] {
  const counts = paths.map((p) => p.reduce<Record<string, number>>((m, t) => ({ ...m, [t]: (m[t] ?? 0) + 1 }), {}))
  return paths.map((p) => {
    const seen: Record<string, number> = {}
    return p.map((tool) => {
      seen[tool] = (seen[tool] ?? 0) + 1
      return { tool, distinctive: counts.some((c) => (c[tool] ?? 0) < seen[tool]) }
    })
  })
}

/** Tools some other path calls that this one never does ("what it did not need to do, or could not do"). */
export function notCalled(paths: string[][]): string[][] {
  const all = new Set(paths.flat())
  return paths.map((p) => [...all].filter((t) => !p.includes(t)))
}

export const distinctPaths = (paths: string[][]) => new Set(paths.map((p) => p.join('>'))).size

export type TaxFacts = { computed_paise: number | null; rows: { amount_paise: number; deductor: string }[] }

const call = (t: TraceView, tool: string) => t.steps.flatMap((s) => s.tool_calls).find((c) => c.tool_name === tool)

/** What the agent actually found: the TDS the rule engine computed, and the rows the tax-credit extract returned. */
export function taxFacts(t: TraceView): TaxFacts {
  const expected = call(t, 'compute_withholding')?.result_json.expected_paise
  const rows = call(t, 'get_authorized_tax_credit_extract')?.result_json.rows
  return {
    computed_paise: typeof expected === 'number' ? expected : null,
    rows: Array.isArray(rows)
      ? rows.map((r: { amount_credited?: number; deductor_name?: string }) => ({ amount_paise: r.amount_credited ?? 0, deductor: r.deductor_name ?? '' }))
      : [],
  }
}

/** The hypotheses the agent revised along the way, in order: "tds (open)", "tds (rejected)". */
export const hypothesisLog = (t: TraceView) =>
  t.steps.flatMap((s) => s.hypotheses.map((h) => ({ kind: h.kind, status: h.status, text: h.text })))
