export function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="lt-stat-tile">
      <div className="lt-stat-tile__value" style={{ fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      <div className="lt-stat-tile__label">{label}</div>
      {hint && <div className="lt-stat-tile__hint">{hint}</div>}
    </div>
  )
}
