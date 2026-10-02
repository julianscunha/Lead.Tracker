import { useEffect, useState } from 'react'
import { listFieldConflicts, resolveFieldConflict, type FieldConflictRow } from '../api'
import { InfoHint } from '../InfoHint'

// Rótulos de negócio (nunca o nome do campo) e das fontes.
const FIELD_LABEL: Record<string, string> = {
  legal_name: 'Razão social', website: 'Site', industry: 'Setor', address: 'Endereço',
  annual_revenue: 'Receita anual', employee_count: 'Nº de funcionários', customer_status: 'Status do cliente',
  segment: 'Segmento', region: 'Região', rep_id: 'Representante',
}
const SOURCE_LABEL: Record<string, string> = {
  salesforce: 'Salesforce', google_maps: 'Google Maps', csv: 'Planilha (CSV)', manual: 'Edição manual',
  mapping: 'Mapeamento de campo', legacy: 'Dado anterior',
}

export function formatConflictValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'vazio'
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).filter(v => v).join(', ') || 'vazio'
  }
  return String(value)
}

export function ConflictsSection() {
  const [conflicts, setConflicts] = useState<FieldConflictRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [repId, setRepId] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const reload = () => listFieldConflicts().then(setConflicts)

  useEffect(() => {
    reload().catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar os conflitos de dados.'))
  }, [])

  const choose = async (id: string, source: string) => {
    setBusyId(id)
    setError(null)
    try {
      await resolveFieldConflict(id, source, repId.trim() || null)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao resolver o conflito.')
    } finally {
      setBusyId(null)
    }
  }

  if (conflicts === null && !error) return <p className="lt-hint">Carregando conflitos…</p>

  return (
    <section className="lt-panel" aria-labelledby="lt-conflicts-title">
      <div className="lt-header lt-header-row">
        <h3 id="lt-conflicts-title">Conflitos de dados</h3>
        <InfoHint text="Quando duas fontes trazem valores diferentes para o mesmo campo de uma empresa, o valor atual continua valendo até você escolher qual manter. A escolha fica registrada no histórico de alterações e não é perguntada de novo." />
      </div>
      {error && <p className="lt-alert" role="alert">{error}</p>}
      {conflicts && conflicts.length === 0 && <p className="lt-hint">Nenhum conflito: as fontes concordam.</p>}
      {conflicts && conflicts.length > 0 && (
        <label className="lt-field">
          <span>Seu id de representante (opcional) <InfoHint text="Aparece no histórico de alterações como quem escolheu." /></span>
          <input value={repId} onChange={e => setRepId(e.target.value)} maxLength={64} />
        </label>
      )}
      {conflicts?.map(c => (
        <div key={c.id} className="lt-panel">
          <strong>{c.company_name} — {FIELD_LABEL[c.field] ?? c.field}</strong>
          <div className="lt-panel-row">
            {c.candidates.map(cand => (
              <button
                key={cand.source} type="button" className="lt-btn" disabled={busyId === c.id}
                onClick={() => choose(c.id, cand.source)}
              >
                Manter "{formatConflictValue(cand.value)}" ({SOURCE_LABEL[cand.source] ?? cand.source})
              </button>
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}
