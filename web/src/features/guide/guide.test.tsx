import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GUIDE_STEPS } from '@/lib/guide'
import { DemoGuide } from './DemoGuide'
import { GuideProvider, useGuide } from './GuideProvider'

const Where = () => <p data-testid="where">{useLocation().pathname}</p>
const Start = () => <button onClick={useGuide().start}>start</button>
const setup = () => render(<MemoryRouter><GuideProvider><Start /><DemoGuide /><Where /></GuideProvider></MemoryRouter>)

beforeEach(() => sessionStorage.clear())

describe('Guided demo', () => {
  it('is closed until started, then walks the script forwards and backwards', async () => {
    setup()
    expect(screen.queryByRole('complementary', { name: 'Guided demo' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('start'))
    expect(screen.getByText(`Guided demo · step 1 of ${GUIDE_STEPS.length}`)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Back/ })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: /Next/ }))
    expect(screen.getByRole('heading', { name: GUIDE_STEPS[1].title })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Back/ }))
    expect(screen.getByRole('heading', { name: GUIDE_STEPS[0].title })).toBeInTheDocument()
  })

  it('navigates to the page a step is about, and clicks Run batch for the batch step', async () => {
    const run = vi.fn()
    document.body.insertAdjacentHTML('beforeend', '<button id="run-batch">Run batch</button>')
    document.getElementById('run-batch')!.addEventListener('click', run)
    setup()
    await userEvent.click(screen.getByText('start'))
    await userEvent.click(screen.getByRole('button', { name: /Next/ }))
    await userEvent.click(screen.getByRole('button', { name: /Run it for me/ }))
    expect(screen.getByTestId('where')).toHaveTextContent('/')
    await vi.waitFor(() => expect(run).toHaveBeenCalledTimes(1))
    document.getElementById('run-batch')!.remove()
    await userEvent.click(screen.getByRole('button', { name: /Next/ }))
    await userEvent.click(screen.getByRole('button', { name: /Open CASE-0007/ }))
    expect(screen.getByTestId('where')).toHaveTextContent('/cases/CASE-0007')
  })

  it('remembers its step across a reload and can be closed, and finishes on the last step', async () => {
    const first = setup()
    await userEvent.click(screen.getByText('start'))
    await userEvent.click(screen.getByRole('button', { name: /Next/ }))
    first.unmount()
    setup()
    expect(screen.getByRole('heading', { name: GUIDE_STEPS[1].title })).toBeInTheDocument() // reopened where it was left
    await userEvent.click(screen.getByRole('button', { name: 'Close the guided demo' }))
    expect(screen.queryByRole('complementary', { name: 'Guided demo' })).not.toBeInTheDocument()
  })

  it('ends with a Finish button instead of Next', async () => {
    sessionStorage.setItem('artemis.guide', JSON.stringify({ active: true, step: GUIDE_STEPS.length - 1 }))
    setup()
    expect(screen.getByRole('button', { name: 'Finish' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Next/ })).not.toBeInTheDocument()
  })
})
