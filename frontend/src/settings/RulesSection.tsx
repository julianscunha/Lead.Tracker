import { useEffect, useState } from 'react'
import { InfoHint } from '../InfoHint'
import { parseBRL } from './logic'
import { RuleSuggestions } from './RuleSuggestions'

import { createRule, deleteRule, listRules, type CorrelationRule, type NewRule, type Product, type Service } from '../api'

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

export function RulesSection({ products, services }: { products: Product[]; services: Service[] }) {
  const [rules, setRules] = useState<CorrelationRule[] | null>(null)
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
  const [dealValue, setDealValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    listRules()
      .then(setRules)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Não consegui carregar as regras.'))
  }, [])

  const categories = Array.from(new Set([...products, ...services].map(i => i.category).filter((c): c is string => !!c)))
  const items = [...products.map(p => ({ id: p.id, label: p.name })), ...services.map(s => ({ id: s.id, label: s.name }))]

  const resetForm = () => {
    setJustification('')
    setDealValue('')
    setRequiresItem(''); setAbsentItem('')
    setRequiresCategory(''); setAbsentCategory('')
  }

  const handleCreate = async () => {
    setSaving(true)
    setSaveError(null)
    const body: NewRule = { opportunity_type: opportunityType, justification }
    const value = parseBRL(dealValue)
    if (dealValue.trim() !== '' && value > 0) body.estimated_deal_value = value
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

  const handleDelete = async (rule: CorrelationRule) => {
    if (!window.confirm(`Remover a regra "${rule.opportunity_type}"? Essa ação não pode ser desfeita.`)) return
    setDeletingId(rule.id)
    setDeleteError(null)
    try {
      await deleteRule(rule.id)
      setRules(prev => (prev ?? []).filter(r => r.id !== rule.id))
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Falha ao remover regra.')
    } finally {
      setDeletingId(null)
    }
  }

  if (loadError) return <p className="lt-alert" role="alert">{loadError}</p>
  if (!rules) return <p className="lt-hint">Carregando regras…</p>

  const dealValueOk = dealValue.trim() === '' || parseBRL(dealValue) > 0
  const canSave = dealValueOk && justification.trim() !== '' && (
    kind === 'relation' || (kind === 'presence' ? requiresItem !== '' : requiresCategory !== '')
  )

  return (
    <div>
      <div className="lt-header lt-header-row">
        <h2>Regras</h2>
        <InfoHint text="Regras determinísticas que detectam oportunidade — sempre por categoria/item real do catálogo, nunca texto livre." />
      </div>
      <div className="lt-toolbar">
        <button type="button" className="lt-btn" onClick={() => setFormOpen(f => !f)}>
          {formOpen ? 'Cancelar' : 'Nova regra'}
        </button>
      </div>
      <RuleSuggestions onCreated={created => setRules(prev => [...(prev ?? []), created])} />

      {formOpen && (
        <div className="lt-source-card__form">
          <label className="lt-field">
            <span>Tipo de regra <InfoHint text="Categoria compara grupos de itens; item específico compara um produto/serviço só; relação reaproveita um vínculo já existente no catálogo." /></span>
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
              <span>Tipo de relação <InfoHint text="Reaproveita a relação entre itens já definida no catálogo de portfólio." /></span>
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
          <label className="lt-field">
            <span>Valor típico da oportunidade, em R$ (opcional) <InfoHint text="Quanto costuma valer um negócio deste tipo, segundo você. O sistema só copia este número para cada oportunidade da regra: não calcula nem prevê nada. Em branco, a oportunidade fica sem valor (aparece como “—”)." /></span>
            <input inputMode="decimal" value={dealValue} onChange={e => setDealValue(e.target.value)} placeholder="ex.: 40000" />
          </label>

          {saveError && <p className="lt-alert" role="alert">{saveError}</p>}
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={handleCreate} disabled={saving || !canSave}>
              {saving ? 'Salvando…' : 'Criar regra'}
            </button>
          </div>
        </div>
      )}

      {deleteError && <p className="lt-alert" role="alert">{deleteError}</p>}
      {rules.length === 0 ? (
        <p className="lt-empty" role="status">Nenhuma regra cadastrada ainda.</p>
      ) : (
        <table className="lt-table">
          <thead>
            <tr><th>Rótulo</th><th>Condição</th><th>Justificativa</th><th>Valor típico</th><th>Ativa</th><th></th></tr>
          </thead>
          <tbody>
            {rules.map(r => (
              <tr key={r.id}>
                <td>{r.opportunity_type}</td>
                <td>{describeRule(r)}</td>
                <td>{r.justification}</td>
                <td>{r.estimated_deal_value ? r.estimated_deal_value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }) : '—'}</td>
                <td>{r.active ? 'Sim' : 'Não'}</td>
                <td>
                  <button type="button" className="lt-btn" onClick={() => handleDelete(r)} disabled={deletingId === r.id}>
                    {deletingId === r.id ? 'Removendo…' : 'Remover'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
