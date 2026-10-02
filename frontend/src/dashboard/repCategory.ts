import type { RepCategoryCell, RepCategoryReach } from '../api'
import { formatPercent as pct } from './format'
import { FUNNEL_REACH_LABELS } from './types'

// Lógica pura da matriz rep×categoria (visão atual, nunca conversão histórica):
// textos, estados e cores ficam aqui pra serem testados sem renderizar nada.

export const REACH_STAGES = ['detected', 'qualified', 'reviewed', 'contacted', 'opportunity']
export const DEFAULT_STAGE = 'contacted'

const stageLabel = (s: string) => FUNNEL_REACH_LABELS[s] ?? s
const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)

export interface CellView {
  kind: 'value' | 'insufficient' | 'none'
  text: string
  intensity: number | null  // 0..1 só em 'value' (domínio fixo 0–100%, nunca normalizado pelo máximo)
  fragile: boolean  // amostra válida mas pequena (n < 2×mínimo): sinaliza fragilidade sem esconder o dado
  ariaLabel: string
  tooltip: string
  opportunityIds: string[]  // os deals por trás da célula (a UI lista ao clicar)
}

export function cellView(
  cell: RepCategoryCell | undefined, rep: string, category: string, stage: string, minSample: number,
  reference: number | null,
): CellView {
  const who = `Representante ${rep}, categoria ${category}`
  if (!cell) {
    return {
      kind: 'none', text: '—', intensity: null, fragile: false, ariaLabel: `${who}: sem oportunidades`,
      tooltip: 'Sem oportunidades neste par.', opportunityIds: [],
    }
  }
  const counts = REACH_STAGES.map(s => `${stageLabel(s)}: ${cell.reachCounts[s] ?? 0}`).join(' · ')
  const ratio = cell.reachRatios[stage]
  if (cell.insufficient || ratio === null || ratio === undefined) {
    return {
      kind: 'insufficient', text: `n=${cell.n}`, intensity: null, fragile: false,
      ariaLabel: `n=${cell.n}: ${who}, dado insuficiente, ${cell.n} de ${minSample} oportunidades necessárias`,
      tooltip: `Dado insuficiente: ${cell.n} de ${minSample} necessárias. Nenhuma leitura é segura — acompanhe o volume ou olhe os deals um a um.\n${counts}`,
      opportunityIds: cell.opportunityIds,
    }
  }
  const count = cell.reachCounts[stage] ?? 0
  const fragile = cell.n < minSample * 2
  const refText = reference === null ? '' : `Mediana do time nesta categoria: ${pct(reference)}.`
  return {
    kind: 'value', text: pct(ratio), intensity: ratio, fragile,
    // Nome acessível começa pelo texto visível (SC 2.5.3 "label in name") e carrega o que o
    // tooltip diria — `title` sozinho não chega a teclado/toque.
    ariaLabel: `${pct(ratio)}: ${who}, ${count} de ${cell.n} chegaram a ${stageLabel(stage)}`
      + `${reference === null ? '' : `, mediana do time ${pct(reference)}`}${fragile ? ', amostra pequena' : ''}`,
    tooltip: [`${count} de ${cell.n} chegaram a ${stageLabel(stage)} ou além.`, counts, refText,
      fragile ? 'Amostra pequena: percentuais com n baixo oscilam muito.' : ''].filter(Boolean).join('\n'),
    opportunityIds: cell.opportunityIds,
  }
}

export interface MatrixView {
  reps: string[]
  categories: string[]
  rows: CellView[][]  // rows[i][j] = reps[i] × categories[j]
  reference: (number | null)[]  // mediana do time por categoria, no estágio escolhido
  summary: string
}

const alpha = (a: string, b: string) => a.localeCompare(b, 'pt-BR')
export const allReps = (d: RepCategoryReach) => [...new Set(d.cells.map(c => c.repId))].sort(alpha)
export const allCategories = (d: RepCategoryReach) => [...new Set(d.cells.map(c => c.category))].sort(alpha)

/** Ordem sempre alfabética (nunca por desempenho — sem ranking de rep). */
export function buildMatrix(
  data: RepCategoryReach, stage: string, hiddenReps: ReadonlySet<string>, hiddenCategories: ReadonlySet<string>,
): MatrixView {
  const reps = allReps(data).filter(r => !hiddenReps.has(r))
  const categories = allCategories(data).filter(c => !hiddenCategories.has(c))
  const byPair = new Map(data.cells.map(c => [`${c.repId}\u0000${c.category}`, c]))
  const reference = categories.map(c => data.teamMedian[c]?.[stage] ?? null)
  const rows = reps.map(rep => categories.map((cat, j) =>
    cellView(byPair.get(`${rep}\u0000${cat}`), rep, cat, stage, data.minSample, reference[j])))
  const insufficient = rows.flat().filter(v => v.kind === 'insufficient').length
  const summary = `${reps.length} ${plural(reps.length, 'representante', 'representantes')}, `
    + `${categories.length} ${plural(categories.length, 'categoria', 'categorias')}, `
    + `${insufficient} ${plural(insufficient, 'par sem dado suficiente', 'pares sem dado suficiente')}`
  return { reps, categories, rows, reference, summary }
}

type RGB = [number, number, number]
// Matiz único; luminosidade é o único canal (sobrevive a daltonismo e escala de
// cinza). "Mais = mais intenso": mais escuro no claro, mais claro no escuro.
const LIGHT: [RGB, RGB] = [[236, 242, 251], [11, 61, 130]]
const DARK: [RGB, RGB] = [[38, 50, 66], [122, 182, 255]]

const mix = (a: RGB, b: RGB, t: number): RGB => [0, 1, 2].map(i => Math.round(a[i] + (b[i] - a[i]) * t)) as RGB

function luminance([r, g, b]: RGB): number {
  const f = (v: number) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4 }
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}

export function contrastRatio(a: RGB, b: RGB): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** Texto preto ou branco, o que tiver mais contraste — nunca abaixo de ~4.58:1. */
export function cellColors(intensity: number, dark: boolean): { background: string; color: string; rgb: RGB } {
  const [from, to] = dark ? DARK : LIGHT
  const rgb = mix(from, to, Math.min(1, Math.max(0, intensity)))
  const color: RGB = contrastRatio(rgb, [0, 0, 0]) >= contrastRatio(rgb, [255, 255, 255]) ? [0, 0, 0] : [255, 255, 255]
  return { background: `rgb(${rgb.join(',')})`, color: `rgb(${color.join(',')})`, rgb }
}
