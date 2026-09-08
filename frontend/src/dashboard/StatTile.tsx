import { InfoHint } from '../InfoHint'

export function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="lt-stat-tile">
      <div className="lt-stat-tile__top">
        <div className="lt-stat-tile__value" style={{ fontVariantNumeric: 'tabular-nums' }}>{value}</div>
        {hint && <InfoHint text={hint} />}
      </div>
      <div className="lt-stat-tile__label">{label}</div>
    </div>
  )
}
