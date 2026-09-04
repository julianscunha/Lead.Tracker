import { describe, expect, it } from 'vitest'
import type { SourceStatus } from '../api'
import { needsCredentialsBeforeEnabling } from './logic'

function source(overrides: Partial<SourceStatus> = {}): SourceStatus {
  return {
    id: 'salesforce', label: 'Salesforce', implemented: true, enabled: false,
    fields: [], last_check: { status: 'unknown', message: '' },
    ...overrides,
  }
}

describe('needsCredentialsBeforeEnabling', () => {
  it('retorna false quando a fonte não tem campos (ex.: Manual)', () => {
    expect(needsCredentialsBeforeEnabling(source({ fields: [] }))).toBe(false)
  })

  it('retorna true quando algum campo obrigatório ainda não tem valor salvo', () => {
    const s = source({
      fields: [
        { key: 'A', label: 'A', help_text: '', secret: false, has_value: true },
        { key: 'B', label: 'B', help_text: '', secret: false, has_value: false },
      ],
    })
    expect(needsCredentialsBeforeEnabling(s)).toBe(true)
  })

  it('retorna false quando todos os campos já têm valor salvo', () => {
    const s = source({
      fields: [
        { key: 'A', label: 'A', help_text: '', secret: false, has_value: true },
        { key: 'B', label: 'B', help_text: '', secret: true, has_value: true },
      ],
    })
    expect(needsCredentialsBeforeEnabling(s)).toBe(false)
  })
})
