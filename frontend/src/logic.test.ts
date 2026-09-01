import { describe, expect, it } from 'vitest'
import { applyFilters, defaultFilters, summarizeFilters } from './Filters'
import { sortRows } from './OpportunityTable'
import { sampleOpportunities } from './sampleData'

describe('sortRows', () => {
  it('ordena por score desc', () => {
    const sorted = sortRows(sampleOpportunities, 'score', 'desc')
    expect(sorted[0].id).toBe('opp-1') // score 0.92, o mais alto
  })

  it('ordena por prioridade asc', () => {
    const sorted = sortRows(sampleOpportunities, 'prioridade', 'asc')
    expect(sorted[0].priority).toBe('baixa')
  })
})

describe('applyFilters', () => {
  it('filtra só clientes', () => {
    const result = applyFilters(sampleOpportunities, { ...defaultFilters, client: 'clientes' })
    expect(result.every(r => r.isCustomer)).toBe(true)
  })

  it('filtra só prospects', () => {
    const result = applyFilters(sampleOpportunities, { ...defaultFilters, client: 'prospects' })
    expect(result.every(r => !r.isCustomer)).toBe(true)
  })

  it('filtra por score mínimo', () => {
    const result = applyFilters(sampleOpportunities, { ...defaultFilters, minScore: 0.8 })
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('opp-1')
  })

  it('nunca perde oportunidade sem filtro ativo', () => {
    const result = applyFilters(sampleOpportunities, defaultFilters)
    expect(result).toHaveLength(sampleOpportunities.length)
  })
})

describe('summarizeFilters', () => {
  it('sem filtro ativo diz "sem filtro"', () => {
    expect(summarizeFilters(defaultFilters)).toBe('sem filtro')
  })

  it('descreve os filtros ativos', () => {
    const result = summarizeFilters({ ...defaultFilters, client: 'clientes', minScore: 0.5 })
    expect(result).toContain('clientes atuais')
    expect(result).toContain('score mínimo: 0.5')
  })
})
