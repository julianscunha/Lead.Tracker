import { useState } from 'react'
import { createRule, suggestRules, type CorrelationRule, type RuleSuggestion } from '../api'
import { InfoHint } from '../InfoHint'
import { describeSuggestion, parseBRL } from './logic'

type Card = RuleSuggestion & { key: number; value: string; saving: boolean; error: string | null }

// Todo texto aqui vem da IA: é sempre renderizado como TEXTO (React escapa), nunca como HTML.
// A IA só sugere; nada vira regra sem o operador clicar em Aceitar em cada cartão.
export function RuleSuggestions({ onCreated }: { onCreated: (rule: CorrelationRule) => void }) {
  const [cards, setCards] = useState<Card[] | null>(null)
  const [discarded, setDiscarded] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ask = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await suggestRules()
      setCards(result.suggestions.map((s, key) => ({ ...s, key, value: '', saving: false, error: null })))
      setDiscarded(result.discarded)
    } catch (err) {
      setCards(null)
      setError(err instanceof Error ? err.message : 'Não foi possível pedir sugestões agora.')
    } finally {
      setLoading(false)
    }
  }

  const patch = (key: number, p: Partial<Card>) => setCards(prev => (prev ?? []).map(c => (c.key === key ? { ...c, ...p } : c)))

  const accept = async (card: Card) => {
    const value = parseBRL(card.value)
    if (card.value.trim() !== '' && !(value > 0)) {
      patch(card.key, { error: 'Informe um valor maior que zero ou deixe em branco.' })
      return
    }
    patch(card.key, { saving: true, error: null })
    try {
      const created = await createRule({
        opportunity_type: card.opportunity_type, justification: card.justification,
        requires: card.requires, absent: card.absent,
        requires_category: card.requires_category, absent_category: card.absent_category,
        relation_type: card.relation_type,
        ...(card.value.trim() !== '' ? { estimated_deal_value: value } : {}),
      })
      setCards(prev => (prev ?? []).filter(c => c.key !== card.key))
      onCreated(created)
    } catch (err) {
      patch(card.key, { saving: false, error: err instanceof Error ? err.message : 'Falha ao criar a regra.' })
    }
  }

  return (
    <div className="lt-panel">
      <div className="lt-header lt-header-row">
        <h3>Sugerir regras com IA</h3>
        <InfoHint text="Opcional. A IA configurada lê só os nomes, categorias e relações do seu portfólio (nenhum dado de clientes) e propõe regras. Nada vale sem você aceitar cada uma, e a regra manual continua disponível." />
      </div>
      <div className="lt-toolbar">
        <button type="button" className="lt-btn" onClick={ask} disabled={loading} aria-busy={loading}>
          {loading ? 'Pensando…' : 'Sugerir regras com IA'}
        </button>
      </div>
      {error && <p className="lt-alert" role="alert">{error}</p>}
      {cards !== null && (
        <p className="lt-hint" role="status">
          {cards.length === 0 ? 'Nenhuma sugestão nova.' : `${cards.length} sugestão(ões). Confira antes de aceitar.`}
          {discarded > 0 ? ` ${discarded} descartadas por não usarem o seu portfólio.` : ''}
        </p>
      )}
      {cards !== null && cards.length > 0 && (
        <ul>
          {cards.map(c => (
            <li key={c.key} className="lt-panel-row">
              <strong>{c.opportunity_type}</strong>
              <span className="lt-badge">Sugestão da IA — confira antes de aceitar</span>
              <p>{describeSuggestion(c)}</p>
              <p className="lt-hint">{c.justification}</p>
              <label className="lt-field">
                <span>Valor típico, em R$ (opcional)</span>
                <input inputMode="decimal" value={c.value} onChange={e => patch(c.key, { value: e.target.value })} placeholder="ex.: 40000" />
              </label>
              {c.error && <p className="lt-alert" role="alert">{c.error}</p>}
              <div className="lt-toolbar">
                <button type="button" className="lt-btn" onClick={() => accept(c)} disabled={c.saving}>
                  {c.saving ? 'Criando…' : 'Aceitar'}
                </button>
                <button type="button" className="lt-btn" onClick={() => setCards(prev => (prev ?? []).filter(x => x.key !== c.key))} disabled={c.saving}>
                  Ignorar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
