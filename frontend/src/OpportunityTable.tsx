import { Fragment, useRef, useState } from 'react'
import { generateEmailDraft, updateCompanyRenewalDate, updateOpportunityQualification, type EmailDraft } from './api'
import type { AccountHealth, Criticality, OpportunityRow, ScopeNote, SeverityBand, SortKey } from './types'

const SCOPE_OPTIONS: { value: ScopeNote; label: string }[] = [
  { value: 'isolado', label: 'Isolado (poucas licenças/sistemas)' },
  { value: 'parcial', label: 'Parcial (parte relevante do parque)' },
  { value: 'generalizado', label: 'Generalizado (maior parte do parque)' },
]

const CRITICALITY_OPTIONS: { value: Criticality; label: string }[] = [
  { value: 'nao_critico', label: 'Não crítico (impacto operacional baixo)' },
  { value: 'critico_interno', label: 'Crítico interno (grave, não visível ao cliente)' },
  { value: 'critico_exposto', label: 'Crítico e exposto (produção/cliente-facing)' },
]

const SEVERITY_LABEL: Record<SeverityBand, string> = {
  baixo: 'Baixo', medio: 'Médio', alto: 'Alto', critico: 'Crítico', nao_avaliado: 'Não avaliado',
}

const HEALTH_LABEL: Record<AccountHealth, string> = {
  verde: 'Saudável', amarela: 'Atenção', vermelha: 'Crítica', dados_insuficientes: 'Dados insuficientes',
}

const QBR_REASON_LABEL: Record<string, string> = {
  imediata: 'revisão imediata — saúde da conta em estado crítico',
  revisao_de_risco: 'saúde comprometida, sem renovação próxima o bastante pra justificar revisão imediata',
  revisao_antes_da_renovacao: 'renovação próxima e a saúde não está em verde — vale revisar antes de decidir',
  revisao_de_acompanhamento: 'acompanhamento de rotina, saúde em atenção',
  revisao_de_rotina: 'nenhum sinal de urgência — cadência de rotina',
  alinhada_a_renovacao: 'conta saudável — revisão alinhada à data de renovação',
}

function toDateInputValue(iso: string | null): string {
  return iso ? iso.slice(0, 10) : ''
}

const PRIORITY_WEIGHT: Record<OpportunityRow['priority'], number> = { alta: 3, média: 2, baixa: 1 }

export function sortRows(rows: OpportunityRow[], key: SortKey, direction: 'asc' | 'desc'): OpportunityRow[] {
  const factor = direction === 'asc' ? 1 : -1
  const value = (r: OpportunityRow): number => {
    switch (key) {
      case 'score': return r.opportunityScore ?? -1
      case 'potencial': return r.financialPotential ?? -1
      case 'prioridade': return PRIORITY_WEIGHT[r.priority]
      case 'confianca': return r.confidenceScore ?? -1
    }
  }
  return [...rows].sort((a, b) => (value(a) - value(b)) * factor)
}

function formatCurrency(value: number | null): string {
  if (value === null) return '—'
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
}

function formatScore(value: number | null): string {
  return value === null ? '—' : value.toFixed(2)
}

function SortHeader({ label, sortKey, current, direction, onSort }: {
  label: string
  sortKey: SortKey
  current: SortKey
  direction: 'asc' | 'desc'
  onSort: (key: SortKey) => void
}) {
  const active = current === sortKey
  return (
    <th aria-sort={active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => onSort(sortKey)}>
        {label}{active ? (direction === 'asc' ? ' ▲' : ' ▼') : ''}
      </button>
    </th>
  )
}

function SeverityQualification({ row, onUpdated }: { row: OpportunityRow; onUpdated: (updated: OpportunityRow) => void }) {
  const [scopeNote, setScopeNote] = useState(row.scopeNote)
  const [criticality, setCriticality] = useState(row.criticality)
  const [severityNote, setSeverityNote] = useState(row.severityNote ?? '')
  const [saveError, setSaveError] = useState<string | null>(null)
  const requestSeq = useRef(0)

  const save = async (next: { scopeNote: ScopeNote | null; criticality: Criticality | null; severityNote: string }) => {
    setSaveError(null)
    const seq = ++requestSeq.current
    try {
      const updated = await updateOpportunityQualification(row.id, {
        scopeNote: next.scopeNote, criticality: next.criticality, severityNote: next.severityNote || null,
      })
      if (seq !== requestSeq.current) return // resposta atrasada de um save anterior — descarta, não reverte o estado mais novo
      onUpdated(updated)
    } catch (err) {
      if (seq !== requestSeq.current) return
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar a qualificação.')
    }
  }

  return (
    <div className="lt-severity">
      <label>
        Alcance do gap
        <select
          value={scopeNote ?? ''}
          onChange={e => {
            const value = (e.target.value || null) as ScopeNote | null
            setScopeNote(value)
            save({ scopeNote: value, criticality, severityNote })
          }}
        >
          <option value="">Não avaliado</option>
          {SCOPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
      <label>
        Criticidade
        <select
          value={criticality ?? ''}
          onChange={e => {
            const value = (e.target.value || null) as Criticality | null
            setCriticality(value)
            save({ scopeNote, criticality: value, severityNote })
          }}
        >
          <option value="">Não avaliado</option>
          {CRITICALITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
      <label>
        Observação (opcional)
        <textarea
          value={severityNote}
          onChange={e => setSeverityNote(e.target.value)}
          onBlur={() => save({ scopeNote, criticality, severityNote })}
        />
      </label>
      <span className={`lt-badge lt-badge--severity-${row.severityBand}`}>
        Severidade: {SEVERITY_LABEL[row.severityBand]}
      </span>
      {saveError && <p className="lt-hint" role="alert">{saveError}</p>}
    </div>
  )
}

function AccountHealthPanel({ row, onRenewalDateUpdated }: { row: OpportunityRow; onRenewalDateUpdated: () => void }) {
  const [renewalDate, setRenewalDate] = useState(toDateInputValue(row.renewalDate))
  const [saveError, setSaveError] = useState<string | null>(null)
  const requestSeq = useRef(0)

  const save = async (value: string) => {
    setSaveError(null)
    const seq = ++requestSeq.current
    try {
      await updateCompanyRenewalDate(row.companyId, value || null)
      if (seq !== requestSeq.current) return
      onRenewalDateUpdated()
    } catch (err) {
      if (seq !== requestSeq.current) return
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar a data de renovação.')
    }
  }

  return (
    <div className="lt-severity">
      <span className={`lt-badge lt-badge--health-${row.accountHealth}`}>
        Saúde da conta: {HEALTH_LABEL[row.accountHealth]}
      </span>
      <span className="lt-hint">
        Próxima revisão sugerida: {row.qbrSuggestedDays === 0 ? 'imediata' : `em ${row.qbrSuggestedDays} dias`}
        {' '}({QBR_REASON_LABEL[row.qbrReason] ?? row.qbrReason})
      </span>
      <label>
        Data de renovação do contrato
        <input
          type="date"
          value={renewalDate}
          onChange={e => setRenewalDate(e.target.value)}
          onBlur={() => save(renewalDate)}
        />
      </label>
      {saveError && <p className="lt-hint" role="alert">{saveError}</p>}
    </div>
  )
}

function RowDetail({ row, onQualificationUpdated, onRenewalDateUpdated }: {
  row: OpportunityRow
  onQualificationUpdated: (updated: OpportunityRow) => void
  onRenewalDateUpdated: () => void
}) {
  const [draftState, setDraftState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [draftError, setDraftError] = useState<string | null>(null)
  const [draft, setDraft] = useState<EmailDraft | null>(null)

  const handleGenerateDraft = async () => {
    setDraftState('loading')
    setDraftError(null)
    try {
      const result = await generateEmailDraft(row)
      setDraft(result)
      setDraftState('idle')
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : 'Falha ao gerar rascunho.')
      setDraftState('error')
    }
  }

  const copyDraft = async () => {
    if (!draft) return
    await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.greeting}\n\n${draft.body}\n\n${draft.cta}`)
  }

  const copySummary = async () => {
    const text = [
      row.companyName,
      row.isCustomer ? 'Cliente' : 'Prospect',
      `Score: ${formatScore(row.opportunityScore)}`,
      `Potencial: ${formatCurrency(row.financialPotential)}`,
      row.justification ?? '',
    ].filter(Boolean).join(' — ')
    await navigator.clipboard.writeText(text)
  }

  return (
    <tr>
      <td colSpan={8} className="lt-detail">
        <dl>
          <dt>Status de cliente</dt>
          <dd>{row.isCustomer ? 'Cliente' : 'Prospect'}</dd>
          <dt>Fontes</dt>
          <dd>{row.sources.map(s => `${s.type} (${Math.round(s.confidence * 100)}%)`).join(', ') || '—'}</dd>
          <dt>Produtos atuais</dt>
          <dd>{row.currentProducts.join(', ') || '—'}</dd>
          <dt>Produtos recomendados</dt>
          <dd>{row.recommendedProducts.join(', ') || '—'}</dd>
          <dt>Serviços recomendados</dt>
          <dd>{row.recommendedServices.join(', ') || '—'}</dd>
          <dt>Potencial financeiro</dt>
          <dd>{formatCurrency(row.financialPotential)}</dd>
          <dt>Scores</dt>
          <dd>
            oportunidade {formatScore(row.opportunityScore)} · estratégico {formatScore(null)} · confiança {formatScore(row.confidenceScore)}
          </dd>
          <dt>Evidências</dt>
          <dd>{row.evidence.join(', ') || '—'}</dd>
          <dt>Insight</dt>
          <dd>{row.justification ?? 'Sem justificativa registrada.'}</dd>
        </dl>
        <AccountHealthPanel row={row} onRenewalDateUpdated={onRenewalDateUpdated} />
        <SeverityQualification row={row} onUpdated={onQualificationUpdated} />
        <div className="lt-detail-actions">
          <button type="button" className="lt-btn" onClick={copySummary}>Copiar</button>
          <button type="button" className="lt-btn" onClick={handleGenerateDraft} disabled={draftState === 'loading'}>
            {draftState === 'loading' ? 'Gerando…' : 'Gerar rascunho'}
          </button>
        </div>
        {draftState === 'error' && <p className="lt-hint" role="alert">{draftError}</p>}
        {draft && (
          <div className="lt-draft" role="status">
            <p><strong>Assunto:</strong> {draft.subject}</p>
            <p>{draft.greeting}</p>
            <p>{draft.body}</p>
            <p>{draft.cta}</p>
            <button type="button" className="lt-btn" onClick={copyDraft}>Copiar rascunho</button>
            <p className="lt-hint">Revise antes de enviar — o rascunho nunca é enviado automaticamente.</p>
          </div>
        )}
      </td>
    </tr>
  )
}

export function OpportunityTable({ rows, onQualificationUpdated, onRenewalDateUpdated }: {
  rows: OpportunityRow[]
  onQualificationUpdated: (updated: OpportunityRow) => void
  onRenewalDateUpdated: () => void
}) {
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setDirection(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setDirection('desc')
    }
  }

  if (rows.length === 0) {
    return <p className="lt-empty" role="status">Nenhuma oportunidade encontrada com os filtros atuais.</p>
  }

  const sorted = sortRows(rows, sortKey, direction)

  return (
    <table className="lt-table">
      <thead>
        <tr>
          <th>Empresa</th>
          <th>Cliente</th>
          <SortHeader label="Score" sortKey="score" current={sortKey} direction={direction} onSort={handleSort} />
          <SortHeader label="Potencial $" sortKey="potencial" current={sortKey} direction={direction} onSort={handleSort} />
          <th>Produto</th>
          <th>Serviço</th>
          <SortHeader label="Prioridade" sortKey="prioridade" current={sortKey} direction={direction} onSort={handleSort} />
          <th>Fontes</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map(row => (
          <Fragment key={row.id}>
            <tr>
              <td>
                <button
                  type="button"
                  className="lt-expand-btn"
                  aria-expanded={expandedId === row.id}
                  aria-label={`${expandedId === row.id ? 'Recolher' : 'Expandir'} detalhes de ${row.companyName}`}
                  onClick={() => setExpandedId(expandedId === row.id ? null : row.id)}
                >
                  {expandedId === row.id ? '▾' : '▸'} {row.companyName}
                </button>
              </td>
              <td>
                <span className={`lt-badge ${row.isCustomer ? 'lt-badge--customer' : 'lt-badge--prospect'}`}>
                  {row.isCustomer ? 'Cliente' : 'Prospect'}
                </span>
              </td>
              <td>{formatScore(row.opportunityScore)}</td>
              <td>{formatCurrency(row.financialPotential)}</td>
              <td>{row.product ?? '—'}</td>
              <td>{row.service ?? '—'}</td>
              <td>{row.priority}</td>
              <td>{row.sources.map(s => s.type).join(', ')}</td>
            </tr>
            {expandedId === row.id && (
              <RowDetail row={row} onQualificationUpdated={onQualificationUpdated} onRenewalDateUpdated={onRenewalDateUpdated} />
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}
