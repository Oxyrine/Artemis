import { describe, expect, it } from 'vitest'
import type { TraceView } from '@/api/types'
import { distinctPaths, hypothesisLog, markPaths, notCalled, taxFacts } from './compare'

const HERO = ['hyp', 'ledger', 'tax', 'propose', 'finish']
const PROBABLE = ['hyp', 'ledger', 'tax', 'hyp', 'propose', 'request', 'finish']
const CONFLICT = ['hyp', 'ledger', 'tax', 'hyp', 'propose', 'finish']

describe('markPaths', () => {
  it('highlights only the calls that not every run makes, counting repeats', () => {
    const [h, p, c] = markPaths([HERO, PROBABLE, CONFLICT])
    expect(h.some((x) => x.distinctive)).toBe(false) // the hero is the baseline: everything it does the others do too
    expect(p.filter((x) => x.distinctive).map((x) => x.tool)).toEqual(['hyp', 'request']) // the 2nd hypothesis and the evidence request
    expect(c.filter((x) => x.distinctive).map((x) => x.tool)).toEqual(['hyp']) // only the revised hypothesis
  })
  it('marks nothing when the runs are identical', () => {
    expect(markPaths([HERO, HERO]).flat().some((x) => x.distinctive)).toBe(false)
  })
})

describe('notCalled and distinctPaths', () => {
  it('lists what each run never did that another run did', () => {
    expect(notCalled([HERO, PROBABLE, CONFLICT])).toEqual([['request'], [], ['request']])
  })
  it('counts distinct sequences, not distinct tools', () => {
    expect(distinctPaths([HERO, PROBABLE, CONFLICT])).toBe(3)
    expect(distinctPaths([HERO, HERO, CONFLICT])).toBe(2)
  })
})

const trace = (calls: [string, Record<string, unknown>][], hyps: { kind: string; status: string; text: string }[] = []) => ({
  steps: [{ step: 1, hypotheses: hyps, tool_calls: calls.map(([tool_name, result_json], i) => ({ id: `T${i}`, tool_name, args_json: {}, result_json, latency_ms: 0 })) }],
}) as unknown as TraceView

describe('taxFacts', () => {
  it('reads the computed TDS and the rows the tax extract returned', () => {
    const t = trace([['compute_withholding', { expected_paise: 2_600_000 }],
      ['get_authorized_tax_credit_extract', { rows: [{ amount_credited: 2_000_000, deductor_name: 'Orion Civil Limited' }] }]])
    expect(taxFacts(t)).toEqual({ computed_paise: 2_600_000, rows: [{ amount_paise: 2_000_000, deductor: 'Orion Civil Limited' }] })
  })
  it('reports an empty extract and a missing calculation as such, not as zero', () => {
    expect(taxFacts(trace([['get_authorized_tax_credit_extract', { rows: [] }]]))).toEqual({ computed_paise: null, rows: [] })
  })
})

it('hypothesisLog keeps the order the agent revised its beliefs in', () => {
  const t = trace([], [{ kind: 'tds', status: 'open', text: 'find out why' }, { kind: 'tds', status: 'rejected', text: 'credit disagrees' }])
  expect(hypothesisLog(t).map((h) => h.status)).toEqual(['open', 'rejected'])
})
