import { useEffect, useState } from 'react'
import { createRepTarget, listRepTargets, type PeriodType, type RepTarget } from '../api'
import { currentPeriodKey, quarterOptions } from './logic'

export function RepTargetsSection() {
  const [periodType, setPeriodType] = useState<PeriodType>('monthly')
  const [periodKey, setPeriodKey] = useState(currentPeriodKey('monthly', new Date()))
  const [targets, setTargets] = useState<RepTarget[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [formOpen, setFormOpen] = useState(false)
  const [repId, setRepId] = useState('')
  const [amount, setAmount] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    setTargets(null)
    listRepTargets(periodType, periodKey)
      .then(setTargets)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Não consegui carregar as metas.'))
  }, [periodType, periodKey])

  const handlePeriodTypeChange = (value: PeriodType) => {
    setPeriodType(value)
    setPeriodKey(currentPeriodKey(value, new Date()))
  }

  const handleCreate = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const created = await createRepTarget({ rep_id: repId, period_type: periodType, period_key: periodKey, target_amount: Number(amount) })
      setTargets(prev => [...(prev ?? []).filter(t => t.rep_id !== created.rep_id), created])
      setFormOpen(false)
      setRepId('')
      setAmount('')
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar meta.')
    } finally {
      setSaving(false)
    }
  }

  const canSave = repId.trim() !== '' && Number(amount) > 0

  return (
    <div>
      <div className="lt-header">
        <h2>Metas por representante</h2>
        <p>Cadastro manual — sem meta definida, potencial financeiro é um número sem contexto pro dashboard.</p>
      </div>
      <div className="lt-toolbar">
        <label className="lt-field">
          <span>Período</span>
          <select value={periodType} onChange={e => handlePeriodTypeChange(e.target.value as PeriodType)}>
            <option value="monthly">Mensal</option>
            <option value="quarterly">Trimestral</option>
          </select>
        </label>
        {periodType === 'monthly' ? (
          <label className="lt-field">
            <span>Mês</span>
            <input type="month" value={periodKey} onChange={e => setPeriodKey(e.target.value)} />
          </label>
        ) : (
          <label className="lt-field">
            <span>Trimestre</span>
            <select value={periodKey} onChange={e => setPeriodKey(e.target.value)}>
              {quarterOptions(new Date()).map(q => <option key={q} value={q}>{q}</option>)}
            </select>
          </label>
        )}
        <button type="button" className="lt-btn" onClick={() => setFormOpen(f => !f)}>
          {formOpen ? 'Cancelar' : 'Nova meta'}
        </button>
      </div>

      {formOpen && (
        <div className="lt-source-card__form">
          <label className="lt-field">
            <span>Id do representante</span>
            <input value={repId} onChange={e => setRepId(e.target.value)} />
          </label>
          <label className="lt-field">
            <span>Meta financeira (R$) pro período selecionado acima</span>
            <input type="number" min="0" value={amount} onChange={e => setAmount(e.target.value)} />
          </label>
          {saveError && <p className="lt-hint" role="alert">{saveError}</p>}
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={handleCreate} disabled={saving || !canSave}>
              {saving ? 'Salvando…' : 'Salvar meta'}
            </button>
          </div>
        </div>
      )}

      {loadError && <p className="lt-hint" role="alert">{loadError}</p>}
      {!loadError && !targets && <p className="lt-hint">Carregando metas…</p>}
      {!loadError && targets && targets.length === 0 && (
        <p className="lt-empty" role="status">Nenhuma meta cadastrada pra {periodKey} ainda.</p>
      )}
      {!loadError && targets && targets.length > 0 && (
        <table className="lt-table">
          <thead>
            <tr><th>Representante</th><th>Meta (R$)</th></tr>
          </thead>
          <tbody>
            {targets.map(t => (
              <tr key={t.rep_id}>
                <td>{t.rep_id}</td>
                <td>{t.target_amount.toLocaleString('pt-BR')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
