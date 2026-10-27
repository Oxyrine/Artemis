// Presentational pieces: no data fetching, styled only through design tokens (src/design/tokens.css).
import { Check, Copy } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { humanize, rupees, STATUS_LABEL } from '@/lib/format'

export function StatusPill({ status }: { status: string | null | undefined }) {
  const s = status ?? 'NONE'
  return <span className="pill" data-status={s}>{STATUS_LABEL[s] ?? humanize(s)}</span>
}

export function TierBadge({ tier }: { tier: string }) {
  return <span className="tier" data-tier={tier} title={`${humanize(tier)} evidence`}>{humanize(tier)}</span>
}

export const Money = ({ paise, className = '' }: { paise: number | null | undefined; className?: string }) =>
  <span className={`tabular-nums ${className}`}>{rupees(paise)}</span>

export const StateBadge = ({ state }: { state: string }) => <Badge variant="outline">{humanize(state)}</Badge>

const MODES: Record<string, { label: string; hint: string }> = {
  demo: { label: 'Demo agent', hint: 'A rule-based stand-in for the model. No LLM was called.' },
  replay: { label: 'Replay', hint: 'A recorded run played back. No LLM was called.' },
  live: { label: 'Live model', hint: 'Investigated by the configured LLM.' },
}

export function ModeBadge({ mode }: { mode: string | null | undefined }) {
  if (!mode) return null
  const m = MODES[mode] ?? { label: humanize(mode), hint: '' }
  return <Badge variant="secondary" title={m.hint}>{m.label}</Badge>
}

export function Tile({ status, count, active, onClick }: { status: string; count: number; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active} data-status={status} aria-label={`${STATUS_LABEL[status]}: ${count} cases`}
      className="tile">
      <span className="outcome-count tabular-nums">{count}</span>
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <span aria-hidden className="size-2.5 rounded-full bg-[var(--tile)]" />
        {STATUS_LABEL[status]}
      </span>
    </button>
  )
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false)
  useEffect(() => {
    if (!done) return
    const t = setTimeout(() => setDone(false), 1500)
    return () => clearTimeout(t)
  }, [done])
  return (
    <button type="button" aria-label={`Copy ${label}`} title={`Copy ${label}`}
      className="inline-flex text-muted-foreground hover:text-foreground"
      onClick={() => navigator.clipboard?.writeText(text).then(() => setDone(true), () => {})}>
      {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
  )
}

export function ErrorBanner({ error, className = '' }: { error: unknown; className?: string }) {
  if (!error) return null
  return (
    <div role="alert" className={`rounded-md border border-[var(--status-conflicting)] bg-[var(--status-conflicting-soft)] p-3 text-sm text-[var(--status-conflicting-fg)] ${className}`}>
      {error instanceof Error ? error.message : 'Something went wrong'}
    </div>
  )
}

export const Section = ({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) => (
  <section className="work-section">
    <div className="work-section-heading">
      <h2>{title}</h2>
      {aside}
    </div>
    {children}
  </section>
)

export function useTitle(title: string) {
  useEffect(() => { document.title = `${title} · Artemis` }, [title])
}
