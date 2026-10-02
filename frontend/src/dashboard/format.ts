export function formatCurrency(v: number): string {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
}
export function formatCount(v: number): string {
  return v.toLocaleString('pt-BR')
}
/** Nunca arredonda um valor real pra "0%" ou "100%": isso esconderia que não é zero (nem total). */
export function formatPercent(v: number): string {
  if (v > 0 && v < 0.005) return '<1%'
  if (v < 1 && v >= 0.995) return '>99%'
  return `${Math.round(v * 100)}%`
}
