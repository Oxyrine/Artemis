import { Compass, FileSearch, GitMerge, Landmark, Scale, ShieldCheck, UserCheck, X } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, buttonVariants } from '@/components/ui/button'
import { HERO_CASE, HERO_FACTS } from '@/lib/guide'
import { rupees } from '@/lib/format'
import { Term } from '@/ui/Term'
import { useGuide } from '../guide/GuideProvider'

const KEY = 'artemis.welcome.hidden'

/** Remembers, per browser, whether the explainer was dismissed. Storage can fail: the explainer then just shows. */
export function useWelcome() {
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem(KEY) === '1' } catch { return false } })
  const set = useCallback((v: boolean) => {
    setHidden(v)
    try { localStorage.setItem(KEY, v ? '1' : '0') } catch { /* ignore */ }
  }, [])
  return { hidden, hide: () => set(true), show: () => set(false) }
}

const STEPS = [
  { icon: GitMerge, title: 'Match', text: 'Plain rules, no AI. Exact payments close themselves; every other receipt becomes a case to investigate.' },
  { icon: FileSearch, title: 'Investigate', text: 'An AI agent reads the ledger, bank lines, emails and tax-department data by calling tools. An engine does all the maths.' },
  { icon: Scale, title: 'Grade', text: 'Each case is graded Verified, Probable, Insufficient or Conflicting from the evidence, not from the model’s confidence.' },
  { icon: UserCheck, title: 'Decide', text: 'Only a named reviewer can apply a case, within their approval limit. A policy engine refuses anything illegal.' },
]

export function Welcome({ onHide }: { onHide: () => void }) {
  const guide = useGuide()
  const f = HERO_FACTS
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <button type="button" className="welcome-close" onClick={onHide} aria-label="Hide this introduction"><X size={16} /></button>
      <div className="welcome-lead">
        <p className="welcome-kicker"><Landmark size={14} />Accounts receivable, explained</p>
        <h2 id="welcome-title">Money arrives. The invoice doesn’t match. Someone has to find out why.</h2>
        <p>Customers rarely pay exactly what the invoice says. They withhold tax, agree credit notes by email, or settle three invoices with one transfer.
          Finance teams spend hours working out each difference. Artemis investigates every mismatch, shows the evidence, and leaves the decision to a named person.</p>
        <div className="welcome-actions">
          <Button onClick={guide.start}><Compass size={15} />Take the guided demo</Button>
          <Link to={`/cases/${HERO_CASE}`} className={buttonVariants({ variant: 'outline' })}>Open the hero case</Link>
        </div>
      </div>

      <figure className="worked-example" aria-label="A worked example">
        <figcaption>A worked example · {f.utr}</figcaption>
        <dl>
          <div><dt>Invoiced (INV-1042 + INV-1043)</dt><dd>{rupees(f.invoiced_paise)}</dd></div>
          <div><dt>Received in the bank</dt><dd>{rupees(f.received_paise)}</dd></div>
          <div className="gap"><dt>The gap (<Term k="variance" />)</dt><dd>{rupees(f.invoiced_paise - f.received_paise)}</dd></div>
        </dl>
        <p>It is exactly 2% <Term k="tds">TDS</Term> the customer withheld and paid to the tax department. Artemis finds it in the <Term k="taxcredit" />, computes it with the rule engine, and closes the case to <strong>₹0 unexplained</strong>.</p>
      </figure>

      <ol className="how-steps">
        {STEPS.map((s, i) => <li key={s.title}><span className="how-icon"><s.icon size={16} /></span><div><h3>{i + 1}. {s.title}</h3><p>{s.text}</p></div></li>)}
      </ol>

      <ul className="trust-row" aria-label="Guarantees">
        <li><ShieldCheck size={15} />The model never calculates money, tax or eligibility</li>
        <li><UserCheck size={15} />Nothing is applied without a named reviewer</li>
        <li><Landmark size={15} />Every step is on a tamper-evident <Term k="ledger">audit ledger</Term></li>
      </ul>
    </section>
  )
}
