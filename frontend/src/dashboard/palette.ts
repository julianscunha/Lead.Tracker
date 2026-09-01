// Paleta categórica validada (dataviz skill, references/palette.md) — o Core
// não define um ramp categórico próprio (só accent/success/warning/danger),
// então usamos a instância de referência já validada (CVD ΔE ≥ 8, ordem fixa).
export const CATEGORICAL: string[] = [
  '#2a78d6', // 1 blue
  '#eb6834', // 2 orange
  '#1baf7a', // 3 aqua
  '#eda100', // 4 yellow
  '#e87ba4', // 5 magenta
  '#008300', // 6 green
  '#4a3aa7', // 7 violet
  '#e34948', // 8 red
]

export const CATEGORICAL_DARK: string[] = [
  '#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767',
]

// Magnitude (barras de uma métrica só) usa um hue único — nunca uma cor por barra
// quando a categoria já está rotulada no eixo (evita legenda desnecessária).
export const SEQUENTIAL_HUE = '#2a78d6'
export const SEQUENTIAL_HUE_DARK = '#3987e5'

export const MAX_CATEGORICAL_SLOTS = 8

/** Agrupa itens além do limite de slots em "Outros" — nunca gera uma 9ª cor. */
export function foldToOther<T extends { value: number }>(items: T[], label: (item: T) => string, maxSlots = MAX_CATEGORICAL_SLOTS): { label: string; value: number }[] {
  if (items.length <= maxSlots) return items.map(i => ({ label: label(i), value: i.value }))
  const head = items.slice(0, maxSlots - 1)
  const tail = items.slice(maxSlots - 1)
  const otherTotal = tail.reduce((sum, i) => sum + i.value, 0)
  return [...head.map(i => ({ label: label(i), value: i.value })), { label: 'Outros', value: otherTotal }]
}
