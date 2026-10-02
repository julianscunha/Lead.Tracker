import { InfoHint } from '../InfoHint'

/** `tone="attention"` + `action`: card acionável (ex.: triagem atrasada) — só
 * ganha destaque quando há algo a fazer, com frase de decisão, nunca alarme. */
export function StatTile({ label, value, hint, tone, action }: {
  label: string; value: string; hint?: string; tone?: 'attention'; action?: string
}) {
  return (
    <div className={`lt-stat-tile${tone === 'attention' ? ' lt-stat-tile--attention' : ''}`}>
      <div className="lt-stat-tile__top">
        <div className="lt-stat-tile__value" style={{ fontVariantNumeric: 'tabular-nums' }}>{value}</div>
        {hint && <InfoHint text={hint} />}
      </div>
      <div className="lt-stat-tile__label">{label}</div>
      {tone === 'attention' && action && <div className="lt-stat-tile__action">{action}</div>}
    </div>
  )
}
