import { InfoHint } from '../InfoHint'

/** `tone="attention"` + `action`: card acionável (ex.: triagem atrasada) — só
 * ganha destaque quando há algo a fazer, com frase de decisão, nunca alarme. */
export function StatTile({ label, value, hint, tone, action, onClick, linkLabel }: {
  label: string; value: string; hint?: string; tone?: 'attention'; action?: string
  /** Atalho do cartão (ex.: "Triagem atrasada" abre a lista já filtrada). Vira um botão próprio, irmão do (i):
   * nunca um botão dentro de outro. O cartão inteiro responde ao clique por CSS (::after do botão). */
  onClick?: () => void
  linkLabel?: string
}) {
  return (
    <div className={`lt-stat-tile${tone === 'attention' ? ' lt-stat-tile--attention' : ''}${onClick ? ' lt-stat-tile--link' : ''}`}>
      <div className="lt-stat-tile__top">
        <div className="lt-stat-tile__value" style={{ fontVariantNumeric: 'tabular-nums' }}>{value}</div>
        {hint && <InfoHint text={hint} />}
      </div>
      <div className="lt-stat-tile__label">{label}</div>
      {onClick && (
        <button type="button" className="lt-stat-tile__go" onClick={onClick}>
          {linkLabel ?? 'Ver na lista →'}
        </button>
      )}
      {tone === 'attention' && action && <div className="lt-stat-tile__action">{action}</div>}
    </div>
  )
}
