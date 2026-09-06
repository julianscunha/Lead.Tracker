import type { PeriodType, SourceStatus } from '../api'

/** Decide se o toggle deve abrir o formulário de credencial (falta valor
 * obrigatório) ou já pode tentar conectar direto. Lógica pura, sem estado —
 * o componente só chama isso e reage ao resultado. */
export function needsCredentialsBeforeEnabling(source: SourceStatus): boolean {
  return source.fields.some(f => !f.has_value)
}

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
