import { render, renderHook, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { GuideProvider } from '../guide/GuideProvider'
import { Term } from '@/ui/Term'
import { Welcome, useWelcome } from './Welcome'

beforeEach(() => localStorage.clear())

describe('Welcome', () => {
  it('explains the problem with the hero case’s real figures and states the guarantees', () => {
    render(<MemoryRouter><GuideProvider><Welcome onHide={() => {}} /></GuideProvider></MemoryRouter>)
    expect(screen.getByText(/Someone has to find out why/)).toBeInTheDocument()
    expect(screen.getByText('₹15,34,000')).toBeInTheDocument() // invoiced
    expect(screen.getByText('₹15,08,000')).toBeInTheDocument() // received
    expect(screen.getAllByText('₹26,000').length).toBeGreaterThan(0) // the gap
    expect(screen.getByText(/never calculates money/)).toBeInTheDocument()
    expect(screen.getByText(/Nothing is applied without a named reviewer/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open the hero case' })).toHaveAttribute('href', '/cases/CASE-0007')
  })

  it('stays dismissed after a reload, and can be brought back', () => {
    const a = renderHook(() => useWelcome())
    expect(a.result.current.hidden).toBe(false)
    act(() => a.result.current.hide())
    expect(renderHook(() => useWelcome()).result.current.hidden).toBe(true) // a fresh mount reads the stored choice
    act(() => a.result.current.show())
    expect(renderHook(() => useWelcome()).result.current.hidden).toBe(false)
  })
})

describe('Term', () => {
  it('is keyboard-focusable and defaults to the glossary name', () => {
    render(<Term k="tds" />)
    const t = screen.getByText('TDS')
    expect(t).toHaveAttribute('tabindex', '0')
    expect(t).toHaveClass('term')
  })
  it('shows the plain-language definition on focus', async () => {
    render(<Term k="variance">the gap</Term>)
    await userEvent.tab()
    expect(await screen.findByText(/what the invoices add up to and what the bank actually received/)).toBeInTheDocument()
  })
})
