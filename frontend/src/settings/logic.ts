import type { PeriodType } from '../api'

/** Mesma regra de core/opportunity_engine.py::current_period_key —
 * duplicada aqui só pra pré-preencher o formulário de meta com o período
 * corrente; o backend é quem decide o período de verdade ao gravar. */
export function currentPeriodKey(periodType: PeriodType, today: Date): string {
  const year = today.getFullYear()
  if (periodType === 'quarterly') {
    const quarter = Math.floor(today.getMonth() / 3) + 1
    return `${year}-Q${quarter}`
  }
  const month = String(today.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

/** Opções de trimestre pro seletor de meta (ano corrente + próximo, 8
 * opções) — achado da revisão de código: um `<input>` de texto livre pra
 * period_key deixava o usuário digitar qualquer coisa, e o backend não
 * validava, criando meta "órfã" (nunca casa com nenhum período real,
 * degrada silenciosamente pra "sem meta definida"). Um `<select>` torna
 * o formato inválido irrepresentável, mais barato que validar depois. */
export function quarterOptions(today: Date): string[] {
  const year = today.getFullYear()
  return [year, year + 1].flatMap(y => [1, 2, 3, 4].map(q => `${y}-Q${q}`))
}

// "40.000", "40.000,50" e "40000.5" (pt-BR ou simples); qualquer outra coisa, inclusive infinito, vira NaN.
export const parseBRL = (s: string) => {
  const t = s.trim()
  const n = Number(/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(t) ? t.replace(/\./g, '').replace(',', '.') : t.replace(',', '.'))
  return Number.isFinite(n) ? n : NaN
}

type SuggestedRule = {
  requires_labels: string[]; absent_labels: string[]; requires_category: string[]
  absent_category: string[]; relation_type: string | null
}

/** Regra sugerida em linguagem legível (nomes do portfólio, nunca ids). */
export function describeSuggestion(s: SuggestedRule): string {
  if (s.relation_type) {
    return s.relation_type === 'substitute'
      ? 'Quando a empresa tem um item com substituto cadastrado no portfólio'
      : 'Quando a empresa tem um item com pré-requisito cadastrado no portfólio'
  }
  const has = [...s.requires_labels, ...s.requires_category.map(c => `categoria ${c}`)]
  const lacks = [...s.absent_labels, ...s.absent_category.map(c => `categoria ${c}`)]
  return `Quando a empresa tem ${has.join(' e ')}${lacks.length ? ` e não tem ${lacks.join(' nem ')}` : ''}`
}
