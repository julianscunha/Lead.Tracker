import { describe, expect, it } from 'vitest'
import { foldToOther, MAX_CATEGORICAL_SLOTS } from './palette'

describe('foldToOther', () => {
  it('não mexe quando cabe nos slots', () => {
    const items = [{ value: 1 }, { value: 2 }]
    const result = foldToOther(items, () => 'x')
    expect(result).toHaveLength(2)
  })

  it('agrupa o excedente em "Outros" sem gerar uma 9ª cor', () => {
    const items = Array.from({ length: 10 }, (_, i) => ({ value: i + 1 }))
    const result = foldToOther(items, i => `item-${i.value}`)

    expect(result).toHaveLength(MAX_CATEGORICAL_SLOTS)
    expect(result[result.length - 1].label).toBe('Outros')
  })

  it('soma corretamente o valor agrupado em "Outros"', () => {
    const items = Array.from({ length: 10 }, (_, i) => ({ value: 1 }))
    const result = foldToOther(items, () => 'item')
    const outros = result[result.length - 1]
    // 10 itens, 7 slots nomeados + 1 "Outros" com os 3 restantes
    expect(outros.value).toBe(3)
  })
})
