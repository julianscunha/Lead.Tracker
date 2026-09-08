import { describe, expect, it } from 'vitest'
import { currentPeriodKey, quarterOptions } from './logic'

describe('currentPeriodKey', () => {
  it('formata mensal como YYYY-MM', () => {
    expect(currentPeriodKey('monthly', new Date(2026, 2, 5))).toBe('2026-03')
  })

  it('mapeia mês pro trimestre calendário correto', () => {
    expect(currentPeriodKey('quarterly', new Date(2026, 0, 15))).toBe('2026-Q1')
    expect(currentPeriodKey('quarterly', new Date(2026, 3, 1))).toBe('2026-Q2')
    expect(currentPeriodKey('quarterly', new Date(2026, 8, 5))).toBe('2026-Q3')
    expect(currentPeriodKey('quarterly', new Date(2026, 11, 31))).toBe('2026-Q4')
  })
})

describe('quarterOptions', () => {
  it('lista os 4 trimestres do ano corrente seguidos dos 4 do próximo, em ordem cronológica', () => {
    expect(quarterOptions(new Date(2026, 5, 1))).toEqual([
      '2026-Q1', '2026-Q2', '2026-Q3', '2026-Q4', '2027-Q1', '2027-Q2', '2027-Q3', '2027-Q4',
    ])
  })
})
