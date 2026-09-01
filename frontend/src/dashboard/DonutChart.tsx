import { CATEGORICAL, foldToOther } from './palette'
import { ChartTooltip, useTooltip } from './Tooltip'

export interface DonutDatum { label: string; value: number }

const SIZE = 140
const RADIUS = 60
const STROKE = 22
const CENTER = SIZE / 2

function polarToCartesian(angleDeg: number): [number, number] {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return [CENTER + RADIUS * Math.cos(rad), CENTER + RADIUS * Math.sin(rad)]
}

function arcPath(startAngle: number, endAngle: number): string {
  const [x1, y1] = polarToCartesian(startAngle)
  const [x2, y2] = polarToCartesian(endAngle)
  const largeArc = endAngle - startAngle > 180 ? 1 : 0
  return `M ${x1} ${y1} A ${RADIUS} ${RADIUS} 0 ${largeArc} 1 ${x2} ${y2}`
}

/** Distribuição categórica — donut. Legenda sempre presente (≥2 séries), rótulo
 * direto só nas 4 maiores fatias (seletivo, não em toda fatia pequena). */
export function DonutChart({ data, emptyMessage }: { data: DonutDatum[]; emptyMessage: string }) {
  const { tooltip, setTooltip } = useTooltip()

  if (data.length === 0) {
    return <p className="lt-empty" role="status">{emptyMessage}</p>
  }

  const folded = foldToOther(data, d => d.label)
  const total = folded.reduce((sum, d) => sum + d.value, 0) || 1

  let cursor = 0
  const segments = folded.map((d, i) => {
    const startAngle = cursor
    const sweep = (d.value / total) * 360
    cursor += sweep
    return { ...d, startAngle, endAngle: cursor, color: CATEGORICAL[i % CATEGORICAL.length] }
  })

  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'center', position: 'relative' }}>
      <svg width={SIZE} height={SIZE} role="img" aria-label={folded.map(d => `${d.label}: ${d.value}`).join('; ')}>
        {segments.map(s => (
          <path
            key={s.label}
            d={arcPath(s.startAngle, s.endAngle)}
            fill="none"
            stroke={s.color}
            strokeWidth={STROKE}
            onMouseEnter={e => setTooltip({ x: e.clientX, y: e.clientY, label: s.label, value: `${s.value} (${Math.round((s.value / total) * 100)}%)` })}
            onMouseMove={e => setTooltip({ x: e.clientX, y: e.clientY, label: s.label, value: `${s.value} (${Math.round((s.value / total) * 100)}%)` })}
            onMouseLeave={() => setTooltip(null)}
          />
        ))}
      </svg>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, fontSize: 11, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {segments.map(s => (
          <li key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color, display: 'inline-block' }} aria-hidden="true" />
            <span style={{ color: 'hsl(var(--text))' }}>{s.label}</span>
            <span style={{ color: 'hsl(var(--text-muted))', fontVariantNumeric: 'tabular-nums' }}>
              {Math.round((s.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
      <ChartTooltip tooltip={tooltip} />
    </div>
  )
}
