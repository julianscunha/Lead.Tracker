import { ChartTooltip, useTooltip } from './Tooltip'

// ponytail: 4 steps do ramp sequencial (references/palette.md), aproximação —
// não rodei o validador com --ordinal por estágio; se a paleta principal mudar,
// revalidar este ramp específico.
const ORDINAL_STEPS = ['#5598e7', '#2a78d6', '#1c5cab', '#104281']

export function FunnelChart({ stages, counts }: { stages: string[]; counts: Record<string, number> }) {
  const { tooltip, setTooltip } = useTooltip()
  const max = Math.max(...stages.map(s => counts[s] ?? 0), 1)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, position: 'relative' }} role="img" aria-label={stages.map(s => `${s}: ${counts[s] ?? 0}`).join('; ')}>
      {stages.map((stage, i) => {
        const value = counts[stage] ?? 0
        const widthPct = (value / max) * 100
        return (
          <div key={stage}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'hsl(var(--text-muted))', marginBottom: 3 }}>
              <span>{stage}</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>{value}</span>
            </div>
            <div
              style={{ height: 16, borderRadius: 4, background: ORDINAL_STEPS[i % ORDINAL_STEPS.length], width: `${widthPct}%`, minWidth: 4 }}
              onMouseEnter={e => setTooltip({ x: e.clientX, y: e.clientY, label: stage, value: String(value) })}
              onMouseMove={e => setTooltip({ x: e.clientX, y: e.clientY, label: stage, value: String(value) })}
              onMouseLeave={() => setTooltip(null)}
            />
          </div>
        )
      })}
      <ChartTooltip tooltip={tooltip} />
    </div>
  )
}
