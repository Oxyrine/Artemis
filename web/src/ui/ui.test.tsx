import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { VerifyResultBanner } from '@/features/audit/AuditPage'
import { StatusPill, Tile, TierBadge } from './primitives'

describe('StatusPill', () => {
  it('names every status in words (colour is never the only signal) and sets the token hook', () => {
    const { rerender } = render(<StatusPill status="PROBABLE" />)
    expect(screen.getByText('Probable')).toHaveAttribute('data-status', 'PROBABLE')
    rerender(<StatusPill status="CONFLICTING" />)
    expect(screen.getByText('Conflicting')).toHaveAttribute('data-status', 'CONFLICTING')
    rerender(<StatusPill status={null} />)
    expect(screen.getByText('Not graded')).toHaveAttribute('data-status', 'NONE')
  })
})

describe('TierBadge', () => {
  it('marks the tier so primary, supporting and derived evidence look different', () => {
    render(<><TierBadge tier="primary" /><TierBadge tier="supporting" /><TierBadge tier="derived" /></>)
    expect(screen.getByText('Primary')).toHaveAttribute('data-tier', 'primary')
    expect(screen.getByText('Supporting')).toHaveAttribute('data-tier', 'supporting')
  })
})

describe('Tile', () => {
  it('has an accessible name with the count, and toggles a filter', async () => {
    const onClick = vi.fn()
    render(<Tile status="VERIFIED" count={16} active={false} onClick={onClick} />)
    await userEvent.click(screen.getByRole('button', { name: 'Verified: 16 cases' }))
    expect(onClick).toHaveBeenCalledOnce()
  })
})

describe('VerifyResultBanner', () => {
  it('is green when the chain is intact', () => {
    render(<VerifyResultBanner result={{ schema_version: 1, ok: true, first_broken_seq: null, checked: 573, checkpoints: 1, reason: null }} />)
    expect(screen.getByTestId('verify-ok')).toHaveTextContent('Chain intact: 573 events and 1 signed checkpoint verified.')
  })
  it('is red and names the first broken event when the chain is tampered with', () => {
    render(<VerifyResultBanner result={{ schema_version: 1, ok: false, first_broken_seq: 3, checked: 2, checkpoints: 1, reason: 'hash mismatch at event 3' }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Chain broken at event #3. hash mismatch at event 3')
  })
})
