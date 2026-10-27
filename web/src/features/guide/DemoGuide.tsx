import { ArrowRight, ChevronLeft, ChevronRight, Compass, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { GUIDE_STEPS, WELCOME_EVENT, type GuideLink } from '@/lib/guide'
import { useBatchRunner } from '../dashboard/BatchProvider'
import { useGuide } from './GuideProvider'

const scrollTo = (id: string) => window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150)

/** A floating walkthrough of the five-minute demo. Every step does something visible: it navigates, scrolls, or runs the batch. */
export function DemoGuide() {
  const g = useGuide()
  const navigate = useNavigate()
  const batch = useBatchRunner()
  if (!g.active) return null
  const step = GUIDE_STEPS[g.step]
  const last = g.step === GUIDE_STEPS.length - 1
  const finished = batch.status && !batch.status.running

  function follow(link: GuideLink) {
    navigate(link.to)
    if (link.action === 'show-welcome') {
      window.dispatchEvent(new Event(WELCOME_EVENT)) // reopen the explainer if it was dismissed, then bring it into view
      window.scrollTo({ top: 0, behavior: 'smooth' })
      scrollTo('welcome')
    } else if (link.action === 'run-batch') {
      if (batch.running) return
      // a demo that has already been run has nothing new to investigate: start from the seed state again
      if (batch.nothingNew) batch.resetAndRun('demo')
      else batch.run('demo')
    }
  }

  const label = (l: GuideLink) =>
    l.action !== 'run-batch' ? l.label : batch.running ? 'Running…' : batch.nothingNew ? 'Reset, then run it' : l.label

  return (
    <aside className="guide-panel" aria-label="Guided demo">
      <div className="guide-head">
        <span><Compass size={14} />Guided demo · step {g.step + 1} of {GUIDE_STEPS.length}</span>
        <button type="button" onClick={g.stop} aria-label="Close the guided demo"><X size={15} /></button>
      </div>
      <div className="guide-dots" aria-hidden="true">{GUIDE_STEPS.map((s, i) => <i key={s.id} className={i <= g.step ? 'on' : ''} />)}</div>
      <h2>{step.title}</h2>
      <p>{step.body}</p>
      <div className="guide-links">{step.links.map((l) => (
        <Button key={l.label} size="sm" disabled={l.action === 'run-batch' && batch.running} onClick={() => follow(l)}>{label(l)}<ArrowRight size={14} /></Button>
      ))}</div>
      {step.id === 'batch' && batch.status && (
        <p className="guide-status" role="status">
          {finished ? `Done: ${batch.status.done} of ${batch.status.total} investigated. The outcome tiles now show the result.`
            : `Investigating ${batch.status.done} of ${batch.status.total} cases…`}
        </p>
      )}
      <div className="guide-nav">
        <Button variant="ghost" size="sm" disabled={g.step === 0} onClick={() => g.go(g.step - 1)}><ChevronLeft size={14} />Back</Button>
        {last ? <Button variant="ghost" size="sm" onClick={g.stop}>Finish</Button>
          : <Button variant="ghost" size="sm" onClick={() => g.go(g.step + 1)}>Next<ChevronRight size={14} /></Button>}
      </div>
    </aside>
  )
}
