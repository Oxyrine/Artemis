import { describe, expect, it } from 'vitest'
import { amount, humanize, rupees, shortHash } from './format'

describe('format', () => {
  it('formats paise as Indian-grouped rupees', () => {
    expect(rupees(150_800_000)).toBe('₹15,08,000')
    expect(rupees(2_600_000)).toBe('₹26,000')
    expect(rupees(12_345)).toBe('₹123.45')
    expect(rupees(-100_000)).toBe('-₹1,000')
    expect(rupees(null)).toBe('—')
  })
  it('formats bare amounts for tables', () => {
    expect(amount(153_400_000)).toBe('15,34,000')
    expect(amount(0)).toBe('0')
  })
  it('humanizes enums and shortens hashes', () => {
    expect(humanize('credit_note')).toBe('Credit note')
    expect(humanize('AUTO_CLOSED')).toBe('Auto closed')
    expect(humanize('tds')).toBe('TDS')
    expect(humanize('tds_receivable')).toBe('TDS receivable')
    expect(shortHash('abcdef0123456789')).toBe('abcdef01')
  })
})
