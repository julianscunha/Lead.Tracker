import { describe, expect, it } from 'vitest'
import type { RepCategoryCell, RepCategoryReach } from '../api'
import { allCategories, allReps, buildMatrix, cellColors, cellView, contrastRatio } from './repCategory'

const STAGES = ['detected', 'qualified', 'reviewed', 'contacted', 'opportunity']

function cell(repId: string, category: string, n: number, contacted: number, insufficient = false): RepCategoryCell {
  const reachCounts = { detected: n, qualified: n, reviewed: n, contacted, opportunity: 0 }
  const reachRatios = Object.fromEntries(STAGES.map(s => [s, insufficient ? null : reachCounts[s as keyof typeof reachCounts] / n]))
  return { repId, category, n, insufficient, reachCounts, reachRatios, opportunityIds: [] }
}

const data = (cells: RepCategoryCell[], teamMedian: RepCategoryReach['teamMedian'] = {}): RepCategoryReach =>
  ({ minSample: 5, unassignedCount: 0, cells, teamMedian })

describe('cellView', () => {
  it('par insuficiente nunca vira 0% nem usa a rampa', () => {
    const v = cellView(cell('Ana', 'Backup', 3, 0, true), 'Ana', 'Backup', 'contacted', 5, null)
    expect(v.kind).toBe('insufficient')
    expect(v.text).toBe('n=3')
    expect(v.intensity).toBeNull()
    expect(v.ariaLabel).toContain('3 de 5')
    expect(v.ariaLabel.startsWith(v.text)).toBe(true)
    expect(v.text).not.toContain('%')
  })

  it('0% real com amostra suficiente é um valor, distinto de insuficiente', () => {
    const v = cellView(cell('Ana', 'Backup', 10, 0), 'Ana', 'Backup', 'contacted', 5, null)
    expect(v.kind).toBe('value')
    expect(v.text).toBe('0%')
    expect(v.intensity).toBe(0)
  })

  it('razão pequena mas real nunca é arredondada pra 0%, nem quase-total pra 100%', () => {
    const tiny = { ...cell('Ana', 'Backup', 1000, 0), reachCounts: { contacted: 3 }, reachRatios: { contacted: 0.003 } }
    const almost = { ...cell('Ana', 'Backup', 1000, 0), reachCounts: { contacted: 997 }, reachRatios: { contacted: 0.997 } }
    expect(cellView(tiny, 'Ana', 'Backup', 'contacted', 5, null).text).toBe('<1%')
    expect(cellView(almost, 'Ana', 'Backup', 'contacted', 5, null).text).toBe('>99%')
  })

  it('carrega os ids das oportunidades por trás da célula (evidência)', () => {
    const c = { ...cell('Ana', 'Backup', 10, 5), opportunityIds: ['o1', 'o2'] }
    expect(cellView(c, 'Ana', 'Backup', 'contacted', 5, null).opportunityIds).toEqual(['o1', 'o2'])
    expect(cellView(undefined, 'Ana', 'Backup', 'contacted', 5, null).opportunityIds).toEqual([])
  })

  it('par sem oportunidades é "none", sem número', () => {
    const v = cellView(undefined, 'Ana', 'Backup', 'contacted', 5, null)
    expect(v.kind).toBe('none')
    expect(v.text).toBe('—')
  })

  it('aria-label e tooltip trazem contagem bruta e mediana do time quando existe', () => {
    const v = cellView(cell('Ana', 'Backup', 12, 7), 'Ana', 'Backup', 'contacted', 5, 0.5)
    expect(v.ariaLabel.startsWith(v.text)).toBe(true)  // label in name: começa pelo texto visível
    expect(v.ariaLabel).toContain('7 de 12 chegaram a Abordadas')
    expect(v.ariaLabel).toContain('mediana do time 50%')
    expect(v.tooltip).toContain('Mediana do time nesta categoria: 50%')
    expect(v.fragile).toBe(false)  // 12 >= 2×5
  })

  it('amostra válida mas pequena é marcada como frágil, sem esconder o dado', () => {
    const v = cellView(cell('Ana', 'Backup', 6, 3), 'Ana', 'Backup', 'contacted', 5, null)
    expect(v.kind).toBe('value')
    expect(v.fragile).toBe(true)
    expect(v.tooltip).toContain('Amostra pequena')
    expect(v.ariaLabel).toContain('amostra pequena')  // não depende só da borda/marcador visual
  })
})

describe('buildMatrix', () => {
  const d = data(
    [cell('Bia', 'Cloud', 10, 5), cell('Ana', 'Cloud', 3, 0, true), cell('Ana', 'Backup', 10, 8)],
    { Cloud: { contacted: null }, Backup: { contacted: 0.8 } },
  )

  it('ordena rep e categoria em ordem alfabética, nunca por desempenho', () => {
    expect(allReps(d)).toEqual(['Ana', 'Bia'])
    expect(allCategories(d)).toEqual(['Backup', 'Cloud'])
    const m = buildMatrix(d, 'contacted', new Set(), new Set())
    expect(m.reps).toEqual(['Ana', 'Bia'])
    expect(m.categories).toEqual(['Backup', 'Cloud'])
    expect(m.rows[0].map(v => v.kind)).toEqual(['value', 'insufficient'])  // Ana
    expect(m.rows[1].map(v => v.kind)).toEqual(['none', 'value'])  // Bia
  })

  it('referência do time vem por categoria e é null sem mediana', () => {
    expect(buildMatrix(d, 'contacted', new Set(), new Set()).reference).toEqual([0.8, null])
  })

  it('filtros escondem linhas/colunas e o resumo acompanha', () => {
    const m = buildMatrix(d, 'contacted', new Set(['Bia']), new Set(['Backup']))
    expect(m.reps).toEqual(['Ana'])
    expect(m.categories).toEqual(['Cloud'])
    expect(m.summary).toBe('1 representante, 1 categoria, 1 par sem dado suficiente')
  })

  it('resumo no plural', () => {
    expect(buildMatrix(d, 'contacted', new Set(), new Set()).summary)
      .toBe('2 representantes, 2 categorias, 1 par sem dado suficiente')
  })

  it('dado vazio gera matriz vazia sem quebrar', () => {
    const m = buildMatrix(data([]), 'contacted', new Set(), new Set())
    expect(m.rows).toEqual([])
    expect(m.summary).toBe('0 representantes, 0 categorias, 0 pares sem dado suficiente')
  })
})

describe('cellColors', () => {
  it.each([false, true])('texto da célula mantém contraste ≥ 4.5:1 em toda a rampa (dark=%s)', dark => {
    for (let i = 0; i <= 20; i++) {
      const { rgb, color } = cellColors(i / 20, dark)
      const fg = color.match(/\d+/g)!.map(Number) as [number, number, number]
      expect(contrastRatio(rgb, fg)).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('rampa é monotônica: mais valor = mais escuro no claro, mais claro no escuro', () => {
    const lum = (i: number, dark: boolean) => { const [r, g, b] = cellColors(i, dark).rgb; return r + g + b }
    expect(lum(1, false)).toBeLessThan(lum(0, false))
    expect(lum(1, true)).toBeGreaterThan(lum(0, true))
  })

  it('intensidade fora de 0..1 é limitada, nunca extrapola a escala', () => {
    expect(cellColors(5, false).rgb).toEqual(cellColors(1, false).rgb)
    expect(cellColors(-1, false).rgb).toEqual(cellColors(0, false).rgb)
  })
})
