import { describe, expect, it } from 'vitest'
import { applyFilters, defaultFilters, summarizeFilters } from './Filters'
import { CADENCE_REASON_PHRASE, sortRows } from './OpportunityTable'
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

describe('CADENCE_REASON_PHRASE', () => {
  // Achado da verificação ao vivo (Fase G, módulo 7): o verbo da frase tem
  // que bater com o canal real de core/opportunity_engine.py
  // (_CUSTOMER_CADENCE/_PROSPECT_CADENCE) — "Ligar" pra categoria cujo canal
  // é e-mail (ou vice-versa) faz o rep copiar um texto pra usar no canal
  // errado. Duplicar aqui é o mesmo trade-off já aceito em STAGE_ORDER
  // (comentário logo acima, no arquivo original): dá feedback imediato na
  // UI, o backend continua sendo quem decide o canal de verdade.
  const EXPECTED_VERB_BY_CATEGORY_AND_CHANNEL: Record<string, string> = {
    continuidade_uso_atual: 'e-mail', // canal real: email
    gap_portfolio: 'ligar', // canal real: ligação
    prova_social_urgencia: 'linkedin', // canal real: linkedin
    abertura_sinal: 'e-mail', // canal real: email
    reforco_angulo_novo: 'ligar', // canal real: ligação
  }

  it('nunca menciona um canal diferente do canal real da categoria', () => {
    const sampleRow = sampleOpportunities[0]
    for (const [category, expectedWord] of Object.entries(EXPECTED_VERB_BY_CATEGORY_AND_CHANNEL)) {
      const phrase = CADENCE_REASON_PHRASE[category](sampleRow).toLowerCase()
      expect(phrase).toContain(expectedWord)
    }
  })
})
