import type { VarianceClosure } from '@/api/types'
import { amount, humanize } from '@/lib/format'
import { Section } from '@/ui/primitives'

const Row = ({ label, value, strong, muted }: { label: string; value: string; strong?: boolean; muted?: boolean }) => (
  <div className={`flex items-baseline justify-between gap-4 py-1.5 ${strong ? 'border-t font-semibold' : ''} ${muted ? 'text-muted-foreground line-through' : ''}`}>
    <dt>{label}</dt><dd className="tabular-nums">{value}</dd>
  </div>
)

/** The variance closure: invoiced, minus each validated adjustment, equals expected, against received, then unexplained. */
export function ClosureCard({ closure }: { closure: VarianceClosure }) {
  const zero = Math.abs(closure.unexplained_paise) <= 100
  return (
    <Section title="Variance closure">
      <dl className="max-w-md text-sm">
        <Row label="Invoiced" value={amount(closure.invoiced_paise)} />
        {closure.adjustments.map((a, i) => (
          <Row key={i} muted={!a.validated} label={`− ${humanize(a.kind)}${a.validated ? '' : ' (not validated)'}`} value={amount(a.amount_paise)} />
        ))}
        <Row label="Expected" value={amount(closure.expected_paise)} strong />
        <Row label="Received" value={amount(closure.received_paise)} />
      </dl>
      <div className="closure-result">
        <span className="text-sm text-muted-foreground">Unexplained</span>
        <span data-testid="unexplained"
          className={`text-3xl font-semibold tabular-nums ${zero ? 'text-[var(--status-verified-fg)]' : 'text-[var(--status-conflicting-fg)]'}`}>
          ₹{amount(closure.unexplained_paise)}
        </span>
        <span className="text-xs text-muted-foreground">{zero ? 'closes to zero within tolerance' : 'not explained by any validated adjustment'}</span>
      </div>
    </Section>
  )
}
