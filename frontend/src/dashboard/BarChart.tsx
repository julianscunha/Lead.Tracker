import { SEQUENTIAL_HUE } from './palette'
import { ChartTooltip, useTooltip } from './Tooltip'

export interface BarDatum { label: string; value: number }

/** Barras horizontais, hue único — magnitude por categoria já rotulada no eixo,
 * não precisa de uma cor por barra (a categoria já está identificada pelo texto). */
export function BarChart({ data, formatValue, emptyMessage }: {
  data: BarDatum[]
  formatValue: (v: number) => string
  emptyMessage: string
}) {
  const { tooltip, setTooltip } = useTooltip()

  if (data.length === 0) {
    return <p className="lt-empty" role="status">{emptyMessage}</p>
  }

  const max = Math.max(...data.map(d => d.value), 1)

  return (
    <div
      style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 10 }}
      role="img"
      aria-label={data.map(d => `${d.label}: ${formatValue(d.value)}`).join('; ')}
    >
      {data.map(d => (
        <div key={d.label}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'hsl(var(--text-muted))', marginBottom: 3 }}>
            <span>{d.label}</span>
            <span style={{ fontVariantNumeric: 'tabular-nums' }}>{formatValue(d.value)}</span>
          </div>
          <div style={{ height: 8, background: 'hsl(var(--bg-subtle))', borderRadius: 4 }}>
            <div
              style={{
                height: 8, borderRadius: 4, background: SEQUENTIAL_HUE,
                width: `${(d.value / max) * 100}%`,
              }}
              onMouseEnter={e => setTooltip({ x: e.clientX, y: e.clientY, label: d.label, value: formatValue(d.value) })}
              onMouseMove={e => setTooltip({ x: e.clientX, y: e.clientY, label: d.label, value: formatValue(d.value) })}
              onMouseLeave={() => setTooltip(null)}
            />
          </div>
        </div>
      ))}
      <ChartTooltip tooltip={tooltip} />
    </div>
  )
}
