import { describe, expect, it } from 'vitest'
import type { CorrelationRule } from '../api'
import { describeRule } from './RulesSection'

function rule(overrides: Partial<CorrelationRule> = {}): CorrelationRule {
  return {
    id: 'r1', opportunity_type: 'cross-sell', justification: 'j',
    requires: [], absent: [], requires_category: [], absent_category: [],
    relation_type: null, active: true,
    ...overrides,
  }
}

describe('describeRule', () => {
  it('descreve regra de relação', () => {
    expect(describeRule(rule({ relation_type: 'prerequisite' }))).toBe('Relação: prerequisite')
  })

  it('descreve regra de categoria simples', () => {
    expect(describeRule(rule({ requires_category: ['backup'] }))).toBe('Categoria backup')
  })

  it('descreve regra de categoria com ausência', () => {
    const desc = describeRule(rule({ requires_category: ['backup'], absent_category: ['monitoring'] }))
    expect(desc).toBe('Categoria backup sem categoria monitoring')
  })

  it('descreve regra de item simples', () => {
    expect(describeRule(rule({ requires: ['veeam_vbr'] }))).toBe('Item veeam_vbr')
  })

  it('descreve regra de item com ausência', () => {
    const desc = describeRule(rule({ requires: ['veeam_vbr', 'm365'], absent: ['vdc365'] }))
    expect(desc).toBe('Item veeam_vbr, m365 sem vdc365')
  })
})
