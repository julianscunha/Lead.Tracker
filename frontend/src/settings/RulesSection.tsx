import { useEffect, useState } from 'react'
import { createRule, listProducts, listRules, listServices, type CorrelationRule, type NewRule, type Product, type Service } from '../api'

type RuleKind = 'category' | 'presence' | 'relation'

export function describeRule(r: CorrelationRule): string {
  if (r.relation_type) return `Relação: ${r.relation_type}`
  if (r.requires_category.length) {
    const abs = r.absent_category.length ? ` sem categoria ${r.absent_category.join(', ')}` : ''
    return `Categoria ${r.requires_category.join(', ')}${abs}`
  }
  const abs = r.absent.length ? ` sem ${r.absent.join(', ')}` : ''
  return `Item ${r.requires.join(', ')}${abs}`
}

export function RulesSection() {
  const [rules, setRules] = useState<CorrelationRule[] | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const [formOpen, setFormOpen] = useState(false)
  const [kind, setKind] = useState<RuleKind>('category')
  const [opportunityType, setOpportunityType] = useState('cross-sell')
  const [justification, setJustification] = useState('')
  const [requiresItem, setRequiresItem] = useState('')
  const [absentItem, setAbsentItem] = useState('')
  const [requiresCategory, setRequiresCategory] = useState('')
  const [absentCategory, setAbsentCategory] = useState('')
  const [relationType, setRelationType] = useState('prerequisite')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listRules(), listProducts(), listServices()])
      .then(([r, p, s]) => { setRules(r); setProducts(p); setServices(s) })
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Não consegui carregar as regras.'))
  }, [])

  const categories = Array.from(new Set([...products, ...services].map(i => i.category).filter((c): c is string => !!c)))
  const items = [...products.map(p => ({ id: p.id, label: p.name })), ...services.map(s => ({ id: s.id, label: s.name }))]

  const resetForm = () => {
    setJustification('')
    setRequiresItem(''); setAbsentItem('')
    setRequiresCategory(''); setAbsentCategory('')
  }

  const handleCreate = async () => {
    setSaving(true)
    setSaveError(null)
    const body: NewRule = { opportunity_type: opportunityType, justification }
    if (kind === 'presence') {
      body.requires = requiresItem ? [requiresItem] : []
      body.absent = absentItem ? [absentItem] : []
    } else if (kind === 'category') {
      body.requires_category = requiresCategory ? [requiresCategory] : []
      body.absent_category = absentCategory ? [absentCategory] : []
    } else {
      body.relation_type = relationType
    }
    try {
      const created = await createRule(body)
      setRules(prev => [...(prev ?? []), created])
      setFormOpen(false)
      resetForm()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar regra.')
    } finally {
      setSaving(false)
    }
  }

  if (loadError) return <p className="lt-hint" role="alert">{loadError}</p>
  if (!rules) return <p className="lt-hint">Carregando regras…</p>

  const canSave = justification.trim() !== '' && (
    kind === 'relation' || (kind === 'presence' ? requiresItem !== '' : requiresCategory !== '')
  )

  return (
    <div>
      <div className="lt-header">
        <h2>Regras</h2>
        <p>Regras determinísticas que detectam oportunidade — sempre por categoria/item real do catálogo, nunca texto livre.</p>
      </div>
      <div className="lt-toolbar">
        <button type="button" className="lt-btn" onClick={() => setFormOpen(f => !f)}>
          {formOpen ? 'Cancelar' : 'Nova regra'}
        </button>
      </div>

      {formOpen && (
        <div className="lt-source-card__form">
          <label className="lt-field">
            <span>Tipo de regra</span>
            <select value={kind} onChange={e => setKind(e.target.value as RuleKind)}>
              <option value="category">Categoria (tenho X, não tenho Y)</option>
              <option value="presence">Item específico</option>
              <option value="relation">Relação já cadastrada no catálogo</option>
            </select>
          </label>

          {kind === 'category' && (
            <>
              <label className="lt-field">
                <span>Categoria que a empresa precisa ter</span>
                <select value={requiresCategory} onChange={e => setRequiresCategory(e.target.value)}>
                  <option value="">Selecione…</option>
                  {categories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <label className="lt-field">
                <span>Categoria que NÃO deve ter (opcional)</span>
                <select value={absentCategory} onChange={e => setAbsentCategory(e.target.value)}>
                  <option value="">Nenhuma</option>
                  {categories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            </>
          )}

          {kind === 'presence' && (
            <>
              <label className="lt-field">
                <span>Item que a empresa precisa ter</span>
                <select value={requiresItem} onChange={e => setRequiresItem(e.target.value)}>
                  <option value="">Selecione…</option>
                  {items.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}
                </select>
              </label>
              <label className="lt-field">
                <span>Item que NÃO deve ter (opcional)</span>
                <select value={absentItem} onChange={e => setAbsentItem(e.target.value)}>
                  <option value="">Nenhum</option>
                  {items.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}
                </select>
              </label>
            </>
          )}

          {kind === 'relation' && (
            <label className="lt-field">
              <span>Tipo de relação</span>
              <select value={relationType} onChange={e => setRelationType(e.target.value)}>
                <option value="prerequisite">Pré-requisito — gera alerta de risco técnico</option>
                <option value="substitute">Substituto — gera oportunidade de consolidação</option>
              </select>
            </label>
          )}

          <label className="lt-field">
            <span>Rótulo da oportunidade (ex.: cross-sell, consolidation, risk)</span>
            <input value={opportunityType} onChange={e => setOpportunityType(e.target.value)} />
          </label>
          <label className="lt-field">
            <span>Justificativa (aparece na oportunidade gerada)</span>
            <input value={justification} onChange={e => setJustification(e.target.value)} />
          </label>

          {saveError && <p className="lt-hint" role="alert">{saveError}</p>}
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={handleCreate} disabled={saving || !canSave}>
              {saving ? 'Salvando…' : 'Criar regra'}
            </button>
          </div>
        </div>
      )}

      {rules.length === 0 ? (
        <p className="lt-empty" role="status">Nenhuma regra cadastrada ainda.</p>
      ) : (
        <table className="lt-table">
          <thead>
            <tr><th>Rótulo</th><th>Condição</th><th>Justificativa</th><th>Ativa</th></tr>
          </thead>
          <tbody>
            {rules.map(r => (
              <tr key={r.id}>
                <td>{r.opportunity_type}</td>
                <td>{describeRule(r)}</td>
                <td>{r.justification}</td>
                <td>{r.active ? 'Sim' : 'Não'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
