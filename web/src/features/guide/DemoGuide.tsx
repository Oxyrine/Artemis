import { ArrowRight, ChevronLeft, ChevronRight, Compass, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { GUIDE_STEPS, type GuideLink } from '@/lib/guide'
import { useGuide } from './GuideProvider'

/** A floating walkthrough of the five-minute demo. It only navigates and clicks the same buttons a visitor would. */
export function DemoGuide() {
  const g = useGuide()
  const navigate = useNavigate()
  if (!g.active) return null
  const step = GUIDE_STEPS[g.step]
  const last = g.step === GUIDE_STEPS.length - 1

  function follow(link: GuideLink) {
    navigate(link.to)
    if (link.action === 'run-batch') window.setTimeout(() => document.getElementById('run-batch')?.click(), 350)
  }

  return (
    <aside className="guide-panel" aria-label="Guided demo">
      <div className="guide-head">
        <span><Compass size={14} />Guided demo · step {g.step + 1} of {GUIDE_STEPS.length}</span>
        <button type="button" onClick={g.stop} aria-label="Close the guided demo"><X size={15} /></button>
      </div>
      <div className="guide-dots" aria-hidden="true">{GUIDE_STEPS.map((s, i) => <i key={s.id} className={i <= g.step ? 'on' : ''} />)}</div>
      <h2>{step.title}</h2>
      <p>{step.body}</p>
      <div className="guide-links">{step.links.map((l) => <Button key={l.label} size="sm" onClick={() => follow(l)}>{l.label}<ArrowRight size={14} /></Button>)}</div>
      <div className="guide-nav">
        <Button variant="ghost" size="sm" disabled={g.step === 0} onClick={() => g.go(g.step - 1)}><ChevronLeft size={14} />Back</Button>
        {last ? <Button variant="ghost" size="sm" onClick={g.stop}>Finish</Button>
          : <Button variant="ghost" size="sm" onClick={() => g.go(g.step + 1)}>Next<ChevronRight size={14} /></Button>}
      </div>
    </aside>
  )
}
