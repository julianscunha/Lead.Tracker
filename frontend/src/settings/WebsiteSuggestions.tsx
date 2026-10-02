import { useState } from 'react'
import { applyPortfolioSuggestions, suggestPortfolioFromWebsite, type PortfolioSuggestion } from '../api'
import { InfoHint } from '../InfoHint'

type Kind = PortfolioSuggestion['kind']
type Row = PortfolioSuggestion & { selected: boolean }

const KIND_LABEL: Record<Kind, string> = { vendor: 'Fabricante', product: 'Produto', service: 'Serviço' }

// Todo texto aqui vem de um site (dado não confiável) ou da IA: é sempre renderizado como TEXTO
// (React escapa), nunca como HTML. A IA só sugere; nada entra no catálogo sem o operador marcar e aplicar.
export function WebsiteSuggestions({ onApplied }: { onApplied: () => void }) {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [discarded, setDiscarded] = useState(0)
  const [pagesRead, setPagesRead] = useState(0)
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const read = async () => {
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      const result = await suggestPortfolioFromWebsite()
      setRows(result.suggestions.map(s => ({ ...s, selected: !s.already_in_catalog })))
      setDiscarded(result.discarded)
      setPagesRead(result.pages_read)
    } catch (err) {
      setRows(null)
      setError(err instanceof Error ? err.message : 'Não foi possível ler o site informado.')
    } finally {
      setLoading(false)
    }
  }

  const update = (index: number, patch: Partial<Row>) =>
    setRows(prev => (prev ?? []).map((r, i) => (i === index ? { ...r, ...patch } : r)))

  const chosen = (rows ?? []).filter(r => r.selected && !r.already_in_catalog)
  const productWithoutVendor = chosen.some(r => r.kind === 'product' && !(r.vendor_name ?? '').trim())

  const apply = async () => {
    setApplying(true)
    setError(null)
    try {
      const result = await applyPortfolioSuggestions(chosen.map(r => ({ kind: r.kind, name: r.name, vendor_name: r.vendor_name })))
      const total = result.created.vendor + result.created.product + result.created.service
      setMessage(`${total} item(ns) adicionado(s) ao portfólio.`)
      setRows(null)
      onApplied()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao adicionar os itens.')
    } finally {
      setApplying(false)
    }
  }

  return (
    <div className="lt-panel">
      <div className="lt-header lt-header-row">
        <h3>Sugerir pelo meu site</h3>
        <InfoHint text="Lê o site da sua empresa (endereço em Configurações > Website da empresa) e a IA sugere fabricantes, produtos e serviços. Só entram sugestões cujo nome aparece no texto do site, e nada vai para o portfólio sem você marcar e adicionar. Requer IA configurada." />
      </div>
      <div className="lt-toolbar">
        <button type="button" className="lt-btn" onClick={read} disabled={loading} aria-busy={loading}>
          {loading ? 'Lendo o site…' : 'Ler meu site'}
        </button>
      </div>
      {error && <p className="lt-alert" role="alert">{error}</p>}
      {message && <p className="lt-hint" role="status">{message}</p>}
      {rows !== null && rows.length === 0 && (
        <p className="lt-hint">Não encontrei itens com evidência no texto do site ({pagesRead} página(s) lida(s)). Cadastre manualmente.</p>
      )}
      {rows !== null && rows.length > 0 && (
        <>
          <p className="lt-hint">
            {rows.length} sugestão(ões) a partir de {pagesRead} página(s). Revise: nada é adicionado sem você marcar.
            {discarded > 0 ? ` ${discarded} sugestão(ões) da IA foram descartadas por não terem evidência no texto.` : ''}
          </p>
          <ul>
            {rows.map((r, i) => (
              <li key={`${i}:${r.name}`} className="lt-panel-row">
                <label className="lt-toggle">
                  <input
                    type="checkbox" checked={r.selected} disabled={r.already_in_catalog}
                    onChange={e => update(i, { selected: e.target.checked })}
                    aria-label={`Adicionar ${r.name}`}
                  />
                  <span>{r.name}</span>
                </label>
                <label className="lt-field">
                  <span>Tipo</span>
                  <select value={r.kind} disabled={r.already_in_catalog} onChange={e => update(i, { kind: e.target.value as Kind })}>
                    {(Object.keys(KIND_LABEL) as Kind[]).map(k => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
                  </select>
                </label>
                {r.kind === 'product' && (
                  <label className="lt-field">
                    <span>Fabricante</span>
                    <input value={r.vendor_name ?? ''} maxLength={100} disabled={r.already_in_catalog}
                      onChange={e => update(i, { vendor_name: e.target.value })} />
                  </label>
                )}
                {r.already_in_catalog
                  ? <span className="lt-badge">já no portfólio</span>
                  : <span className="lt-hint">“{r.evidence}” — {r.page_url}</span>}
              </li>
            ))}
          </ul>
          {productWithoutVendor && <p className="lt-advisory" role="alert">Todo produto precisa de um fabricante: preencha ou troque o tipo para Serviço.</p>}
          <div className="lt-toolbar">
            <button type="button" className="lt-btn" onClick={apply} disabled={applying || chosen.length === 0 || productWithoutVendor}>
              {applying ? 'Adicionando…' : `Adicionar ${chosen.length} selecionado(s)`}
            </button>
            <button type="button" className="lt-btn" onClick={() => setRows(null)} disabled={applying}>Descartar</button>
          </div>
        </>
      )}
    </div>
  )
}
