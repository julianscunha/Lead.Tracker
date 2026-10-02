import { useEffect, useState } from 'react'
import { listFieldConflicts, resolveFieldConflict, type FieldConflictRow } from '../api'

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

export function ConflictsSection({ repId, onResolved }: { repId: string; onResolved?: () => void }) {
  const [conflicts, setConflicts] = useState<FieldConflictRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
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
      onResolved?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao resolver o conflito.')
    } finally {
      setBusyId(null)
    }
  }

  if (error) return <p className="lt-alert" role="alert">{error}</p>
  // Sem conflito não ocupa tela: o bloco só aparece quando há algo para decidir.
  if (!conflicts || conflicts.length === 0) return null

  return (
    <details className="lt-fold lt-fold--attention" open>
      <summary>
        Conflitos de dados ({conflicts.length}) — fontes que discordam, escolha qual manter
      </summary>
      <div className="lt-fold__body">
        <p className="lt-hint">
          O valor atual continua valendo até você escolher. A escolha fica no histórico de alterações e não é perguntada de novo.
          {repId.trim() ? '' : ' Dica: informe seu nome em "Você é" no topo para ele aparecer no histórico.'}
        </p>
        {conflicts.map(c => (
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
      </div>
    </details>
  )
}
