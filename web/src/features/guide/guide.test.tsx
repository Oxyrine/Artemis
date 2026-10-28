import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GUIDE_STEPS, WELCOME_EVENT } from '@/lib/guide'
import { BatchProvider } from '../dashboard/BatchProvider'
import { DemoGuide } from './DemoGuide'
import { GuideProvider, useGuide } from './GuideProvider'

const run = vi.fn()
const reset = vi.fn()
let states: string[] = []
let batchData: unknown
let runError: Error | null
vi.mock('@/api/hooks', () => ({
  useRunBatch: () => ({ mutate: run, isPending: false, error: runError }),
  useReset: () => ({ mutate: reset, isPending: false, error: null }),
  useBatch: () => ({ data: batchData }),
  useCases: () => ({ data: { cases: states.map((state) => ({ state })) } }),
}))

const Where = () => <p data-testid="where">{useLocation().pathname}</p>
const Start = () => <button onClick={useGuide().start}>start</button>
const setup = () => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><GuideProvider><BatchProvider><Start /><DemoGuide /><Where /></BatchProvider></GuideProvider></MemoryRouter></QueryClientProvider>)
const toStep = async (n: number) => { await userEvent.click(screen.getByText('start')); for (let i = 0; i < n; i++) await userEvent.click(screen.getByRole('button', { name: /Next/ })) }

beforeEach(() => { sessionStorage.clear(); vi.clearAllMocks(); states = ['NEW', 'AUTO_CLOSED']; batchData = undefined; runError = null; Element.prototype.scrollIntoView = vi.fn(); window.scrollTo = vi.fn() })

describe('Guided demo', () => {
  it('shows a failed batch request inside the guide instead of silently returning to Run it for me', async () => {
    runError = new Error('The investigation service is temporarily unavailable. Wait a moment, then retry.')
    setup()
    await toStep(1)
    expect(screen.getByRole('alert')).toHaveTextContent('investigation service is temporarily unavailable')
  })

  it('brings metrics into view on every click, including when the route has not changed', async () => {
    document.body.insertAdjacentHTML('beforeend', '<section id="metrics"></section>')
    setup()
    await toStep(GUIDE_STEPS.length - 1)
    await userEvent.click(screen.getByRole('button', { name: 'See the metrics' }))
    await vi.waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1))
    await userEvent.click(screen.getByRole('button', { name: 'See the metrics' }))
    await vi.waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(2))
    document.getElementById('metrics')!.remove()
  })

  it('can minimize the panel to reach the page underneath and resume at the same step', async () => {
    setup()
    await toStep(2)
    await userEvent.click(screen.getByRole('button', { name: 'Minimize the guided demo' }))
    expect(screen.queryByRole('heading', { name: GUIDE_STEPS[2].title })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Expand the guided demo' }))
    expect(screen.getByRole('heading', { name: GUIDE_STEPS[2].title })).toBeInTheDocument()
  })
  it('is closed until started, then walks the script forwards and backwards', async () => {
    setup()
    expect(screen.queryByRole('complementary', { name: 'Guided demo' })).not.toBeInTheDocument()
    await toStep(0)
    expect(screen.getByText(`Guided demo · step 1 of ${GUIDE_STEPS.length}`)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Back/ })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: /Next/ }))
    expect(screen.getByRole('heading', { name: GUIDE_STEPS[1].title })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Back/ }))
    expect(screen.getByRole('heading', { name: GUIDE_STEPS[0].title })).toBeInTheDocument()
  })

  it('"Show me" brings the explainer back, even if it was dismissed, and scrolls to it', async () => {
    document.body.insertAdjacentHTML('beforeend', '<section id="welcome"></section>')
    const opened = vi.fn()
    window.addEventListener(WELCOME_EVENT, opened)
    setup()
    await toStep(0)
    await userEvent.click(screen.getByRole('button', { name: /Show me/ }))
    expect(opened).toHaveBeenCalledTimes(1)
    expect(window.scrollTo).toHaveBeenCalled()
    await vi.waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalled())
    window.removeEventListener(WELCOME_EVENT, opened)
    document.getElementById('welcome')!.remove()
  })

  it('"Run it for me" starts the demo batch and goes to the dashboard where the progress is', async () => {
    setup()
    await toStep(1)
    await userEvent.click(screen.getByRole('button', { name: /Run it for me/ }))
    expect(run).toHaveBeenCalledTimes(1)
    expect(run.mock.calls[0][0]).toBe('demo')
    expect(reset).not.toHaveBeenCalled()
    expect(screen.getByTestId('where')).toHaveTextContent('/')
  })

  it('on an environment that has already been run it offers to reset first, then runs (no dead end)', async () => {
    states = ['AUTO_CLOSED', 'PENDING_APPROVAL', 'NEEDS_REVIEW']
    reset.mockImplementation((_v: unknown, o: { onSuccess: () => void }) => o.onSuccess())
    setup()
    await toStep(1)
    await userEvent.click(screen.getByRole('button', { name: /Reset, then run it/ }))
    expect(reset).toHaveBeenCalledTimes(1)
    expect(run).toHaveBeenCalledTimes(1) // the batch starts once the reset has succeeded
  })

  it('shows progress while the batch runs, and does not start a second one', async () => {
    batchData = { running: true, done: 12, total: 30, errors: {}, mode: 'demo', replay: false }
    setup()
    await toStep(1)
    expect(screen.getByRole('status')).toHaveTextContent('Investigating 12 of 30 cases…')
    expect(screen.getByRole('button', { name: /Running…/ })).toBeDisabled()
    expect(run).not.toHaveBeenCalled()
  })

  it('says when the batch is done', async () => {
    batchData = { running: false, done: 30, total: 30, errors: {}, mode: 'demo', replay: false }
    setup()
    await toStep(1)
    expect(screen.getByRole('status')).toHaveTextContent('Done: 30 of 30 investigated')
  })

  it('navigates to the page a later step is about', async () => {
    setup()
    await toStep(2)
    await userEvent.click(screen.getByRole('button', { name: /Open CASE-0007/ }))
    expect(screen.getByTestId('where')).toHaveTextContent('/cases/CASE-0007')
  })

  it('remembers its step across a reload and can be closed, and finishes on the last step', async () => {
    const first = setup()
    await toStep(1)
    first.unmount()
    setup()
    expect(screen.getByRole('heading', { name: GUIDE_STEPS[1].title })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Close the guided demo' }))
    expect(screen.queryByRole('complementary', { name: 'Guided demo' })).not.toBeInTheDocument()
    sessionStorage.setItem('artemis.guide', JSON.stringify({ active: true, step: GUIDE_STEPS.length - 1 }))
    setup()
    expect(screen.getByRole('button', { name: 'Finish' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Next/ })).not.toBeInTheDocument()
  })
})
