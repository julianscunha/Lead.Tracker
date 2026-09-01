import { useState } from 'react'

export interface TooltipState {
  x: number
  y: number
  label: string
  value: string
}

/** Tooltip de hover compartilhado por gráficos (dataviz skill: hover é padrão, não opcional). */
export function useTooltip() {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  return { tooltip, setTooltip }
}

export function ChartTooltip({ tooltip }: { tooltip: TooltipState | null }) {
  if (!tooltip) return null
  return (
    <div
      role="tooltip"
      style={{
        position: 'absolute', left: tooltip.x + 8, top: tooltip.y + 8,
        background: 'hsl(var(--bg-elevated))', border: '1px solid hsl(var(--border))',
        borderRadius: 6, padding: '4px 8px', fontSize: 11, pointerEvents: 'none',
        color: 'hsl(var(--text))', zIndex: 10, whiteSpace: 'nowrap',
      }}
    >
      <strong>{tooltip.label}</strong> {tooltip.value}
    </div>
  )
}
