import { describe, expect, it } from 'vitest'
import { derivePriority } from './api'
import { summarizeSync } from './settings/SettingsScreen'

describe('derivePriority', () => {
  it('classifica score >= 0.7 como alta', () => {
    expect(derivePriority(0.7)).toBe('alta')
    expect(derivePriority(0.95)).toBe('alta')
  })

  it('classifica score entre 0.4 e 0.7 como média', () => {
    expect(derivePriority(0.4)).toBe('média')
    expect(derivePriority(0.69)).toBe('média')
  })

  it('classifica score abaixo de 0.4 como baixa', () => {
    expect(derivePriority(0.39)).toBe('baixa')
    expect(derivePriority(0)).toBe('baixa')
  })

  it('trata score null como baixa, nunca quebra', () => {
    expect(derivePriority(null)).toBe('baixa')
  })
})

describe('summarizeSync', () => {
  it('avisa quando nenhuma fonte está habilitada', () => {
    expect(summarizeSync([])).toContain('Nenhuma fonte habilitada')
  })

  it('soma empresas e contatos sincronizados entre fontes', () => {
    const msg = summarizeSync([
      { sourceId: 'salesforce', companiesSynced: 3, contactsSynced: 5, errors: [] },
      { sourceId: 'manual', companiesSynced: 1, contactsSynced: 0, errors: [] },
    ])
    expect(msg).toContain('4 empresa(s)')
    expect(msg).toContain('5 contato(s)')
  })

  it('inclui erros de fonte no resumo sem esconder', () => {
    const msg = summarizeSync([
      { sourceId: 'salesforce', companiesSynced: 0, contactsSynced: 0, errors: ['Falha de autenticação.'] },
    ])
    expect(msg).toContain('Falha de autenticação.')
  })
})
