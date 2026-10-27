// The ONLY place paise become strings. Everything upstream (API, database, tests) is integer paise.
const inrWhole = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const inrExact = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 })
const plain = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

/** 150800000 -> "₹15,08,000"; 12345 -> "₹123.45". Whole rupees drop the ".00". */
export function rupees(paise: number | null | undefined): string {
  if (paise == null) return '—'
  return paise % 100 === 0 ? inrWhole.format(paise / 100) : inrExact.format(paise / 100)
}

/** 150800000 -> "15,08,000" (no symbol, for tables and the variance-closure card). */
export function amount(paise: number | null | undefined): string {
  return paise == null ? '—' : plain.format(paise / 100)
}

export const shortHash = (h: string, n = 8) => h.slice(0, n)

export function dateTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'medium' })
}

const ACRONYMS = new Set(['tds', 'gst', 'utr', 'pan', 'tan', 'gstin'])

/** 'credit_note' -> 'Credit note', 'AUTO_CLOSED' -> 'Auto closed', 'tds' -> 'TDS' */
export function humanize(s: string): string {
  const words = s.replace(/_/g, ' ').toLowerCase().split(' ')
  const out = words.map((w) => (ACRONYMS.has(w) ? w.toUpperCase() : w))
  return out.join(' ').replace(/^./, (c) => c.toUpperCase())
}

export const STATUS_LABEL: Record<string, string> = {
  AUTO_CLOSED: 'Auto-closed', VERIFIED: 'Verified', PROBABLE: 'Probable', INSUFFICIENT: 'Insufficient',
  CONFLICTING: 'Conflicting', NONE: 'Not graded',
}

/** 0.9666 -> "97%", null -> "n/a" */
export const pct = (x: number | null | undefined): string => (x == null ? 'n/a' : `${Math.round(x * 100)}%`)
