import { Fragment, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { InfoHint } from './InfoHint'
import {
  createDoNotContact, exportBusinessCase, listOpportunityAudit, generateEmailDraft, getAiConfig, liftDoNotContact, listDoNotContact, getCompanyContacts, getNextSuggestedTouch, markOutreachTouchSent, updateCompanyRenewalDate,
  updateOpportunityDiscovery, updateOpportunityQualification, updateOpportunityStatus,
  type AuditEntry, type CompanyContact, type DoNotContactEntry, type DoNotContactReason, type EmailDraft, type NextSuggestedTouch,
} from './api'
import { canExportBusinessCase, proseSourceMessage } from './businessCase'
import type { AccountHealth, Criticality, DismissalReason, OpportunityRow, ScopeNote, SeverityBand, SortKey } from './types'

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

// A API já devolve a URL sanitizada (core/normalization.py::normalize_website); aqui é a
// segunda trava antes de virar href — só http(s), nunca javascript:/data:.
export function safeHttpUrl(url: string | null | undefined): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null
}

function websiteLabel(url: string): string {
  return url.replace(/^https?:\/\//i, '').replace(/^www\./i, '').replace(/\/$/, '')
}

function toDateInputValue(iso: string | null): string {
  return iso ? iso.slice(0, 10) : ''
}

// Mesmos 5 valores + OTHER de core/models.py::DismissalReason (consulta ao
// agente Pipeline Analyst) — enum fechado, nunca texto livre, pra permitir
// agregação futura de "por que perdemos oportunidades".
const DISMISSAL_REASON_OPTIONS: { value: DismissalReason; label: string }[] = [
  { value: 'no_evidence', label: 'Sem evidência suficiente' },
  { value: 'not_fit', label: 'Sem fit técnico/comercial' },
  { value: 'not_qualified', label: 'Cliente não qualificado' },
  { value: 'false_positive', label: 'Falso positivo da regra' },
  { value: 'other', label: 'Outro (detalhar na observação)' },
]

const STATUS_OPTIONS: { value: OpportunityRow['status']; label: string }[] = [
  { value: 'detected', label: 'Detectada' },
  { value: 'qualified', label: 'Qualificada' },
  { value: 'reviewed', label: 'Revisada' },
  { value: 'contacted', label: 'Contatada' },
  { value: 'opportunity', label: 'Oportunidade' },
  { value: 'dismissed', label: 'Descartada' },
]

// Mesma ordem/regra de core/opportunity_engine.py::requires_status_change_justification —
// duplicada aqui só pra dar feedback imediato na UI; o backend é quem decide de verdade (422 sem nota).
const STAGE_ORDER: OpportunityRow['status'][] = ['detected', 'qualified', 'reviewed', 'contacted', 'opportunity']

function statusChangeNeedsJustification(oldStatus: OpportunityRow['status'], newStatus: OpportunityRow['status']): boolean {
  if (oldStatus === newStatus) return false
  if (oldStatus === 'dismissed') return newStatus !== 'dismissed'
  const oldIdx = STAGE_ORDER.indexOf(oldStatus)
  const newIdx = STAGE_ORDER.indexOf(newStatus)
  if (oldIdx === -1 || newIdx === -1) return false
  return newIdx - oldIdx >= 2
}

function StatusTransition({ row, onUpdated }: { row: OpportunityRow; onUpdated: (updated: OpportunityRow) => void }) {
  const [pendingStatus, setPendingStatus] = useState<OpportunityRow['status'] | null>(null)
  const [note, setNote] = useState('')
  const [dismissalReason, setDismissalReason] = useState<DismissalReason | ''>('')
  const [skipReason, setSkipReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Sair de "detectada" exige discovery preenchida (acima) ou justificativa pra seguir sem ela — o backend decide.
  const leavingDetected = row.status === 'detected' && pendingStatus !== null && pendingStatus !== 'dismissed'
  const needsNote = pendingStatus !== null && statusChangeNeedsJustification(row.status, pendingStatus)
  const needsDismissalReason = pendingStatus === 'dismissed'
  const needsConfirm = needsNote || needsDismissalReason || leavingDetected

  const submit = async (value: OpportunityRow['status'], noteValue: string | null, reasonValue: DismissalReason | null) => {
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await updateOpportunityStatus(row.id, value, noteValue, reasonValue, skipReason.trim() || null)
      onUpdated(updated)
      setPendingStatus(null)
      setNote('')
      setDismissalReason('')
      setSkipReason('')
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Falha ao mudar o status.')
    } finally {
      setSaving(false)
    }
  }

  const handleSelect = (value: OpportunityRow['status']) => {
    setSaveError(null)
    if (value === row.status) {
      setPendingStatus(null)
      return
    }
    setPendingStatus(value)
    if (value !== 'dismissed' && row.status !== 'detected' && !statusChangeNeedsJustification(row.status, value)) void submit(value, null, null)
  }

  return (
    <div className="lt-severity">
      <label className="lt-field">
        <span>Status <InfoHint text="Etapa atual no funil — detectada → qualificada → revisada → contatada → oportunidade." /></span>
        <select value={pendingStatus ?? row.status} onChange={e => handleSelect(e.target.value as OpportunityRow['status'])} disabled={saving}>
          {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
      {row.status === 'dismissed' && pendingStatus === null && row.dismissalReason && (
        <p className="lt-hint">
          Motivo do descarte: {DISMISSAL_REASON_OPTIONS.find(o => o.value === row.dismissalReason)?.label ?? row.dismissalReason}
        </p>
      )}
      {needsDismissalReason && (
        <label className="lt-field">
          <span>Motivo do descarte <InfoHint text="Obrigatório pra descartar — fica registrado no histórico da oportunidade." /></span>
          <select value={dismissalReason} onChange={e => setDismissalReason(e.target.value as DismissalReason)}>
            <option value="">Selecione um motivo</option>
            {DISMISSAL_REASON_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      )}
      {needsNote && (
        <label className="lt-field">
          <span>Justificativa (pulou etapas ou reabriu uma oportunidade descartada) <InfoHint text="Explica por que a mudança fugiu do fluxo normal — fica registrada no histórico." /></span>
          <textarea value={note} onChange={e => setNote(e.target.value)} />
        </label>
      )}
      {leavingDetected && (
        <label className="lt-field">
          <span>Qualificar sem discovery (opcional) <InfoHint text="Só se não der pra preencher a discovery acima — a justificativa fica registrada e a oportunidade aparece como &quot;sem discovery&quot;." /></span>
          <textarea value={skipReason} onChange={e => setSkipReason(e.target.value)} />
        </label>
      )}
      {needsConfirm && (
        <button
          type="button"
          className="lt-btn"
          onClick={() => submit(pendingStatus as OpportunityRow['status'], note || null, dismissalReason || null)}
          disabled={saving || (needsNote && !note.trim()) || (needsDismissalReason && !dismissalReason)}
        >
          Confirmar mudança
        </button>
      )}
      {saveError && <p className="lt-alert" role="alert">{saveError}</p>}
    </div>
  )
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

const DISCOVERY_FIELDS = [
  { key: 'rootCauseStated', label: 'Por que isso acontece hoje?', help: "Com as palavras do cliente. Não o sintoma ('é lento'), mas a causa ('a plataforma não escala')." },
  { key: 'triggerEvent', label: 'Por que agora?', help: 'O que mudou que torna isto prioridade neste trimestre? Auditoria, contrato vencendo, incidente, crescimento.' },
  { key: 'championStake', label: 'O que o seu contato ganha ou perde com isso?', help: 'O que está em jogo para essa pessoa: uma meta, uma apresentação, a reputação dela?' },
] as const

function DiscoveryFields({ row, repId, onUpdated }: { row: OpportunityRow; repId: string; onUpdated: (updated: OpportunityRow) => void }) {
  const [values, setValues] = useState({
    rootCauseStated: row.rootCauseStated ?? '', triggerEvent: row.triggerEvent ?? '', championStake: row.championStake ?? '',
  })
  const [saveError, setSaveError] = useState<string | null>(null)

  const save = async () => {
    setSaveError(null)
    try {
      onUpdated(await updateOpportunityDiscovery(row.id, values, repId.trim() || null))
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar a discovery.')
    }
  }

  return (
    <div className="lt-severity">
      {row.discoveryPending && <p className="lt-hint">Discovery pendente — esta oportunidade avançou sem os 3 campos abaixo.</p>}
      {row.discoverySkipped && <p className="lt-hint">Qualificada sem discovery: {row.discoverySkipReason}</p>}
      {DISCOVERY_FIELDS.map(f => (
        <label key={f.key} className="lt-field">
          <span>{f.label} <InfoHint text={f.help} /></span>
          <textarea
            value={values[f.key]}
            onChange={e => setValues(v => ({ ...v, [f.key]: e.target.value }))}
            onBlur={save}
          />
        </label>
      ))}
      {saveError && <p className="lt-alert" role="alert">{saveError}</p>}
    </div>
  )
}

function SeverityQualification({ row, repId, onUpdated }: { row: OpportunityRow; repId: string; onUpdated: (updated: OpportunityRow) => void }) {
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
      }, repId.trim() || null)
      if (seq !== requestSeq.current) return // resposta atrasada de um save anterior — descarta, não reverte o estado mais novo
      onUpdated(updated)
    } catch (err) {
      if (seq !== requestSeq.current) return
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar a qualificação.')
    }
  }

  return (
    <div className="lt-severity">
      <label className="lt-field">
        <span>Alcance do gap <InfoHint text="Quão abrangente é o gap identificado — usado no cálculo de severidade." /></span>
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
      <label className="lt-field">
        <span>Criticidade <InfoHint text="Quão urgente é o risco pro cliente — usado no cálculo de severidade." /></span>
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
      <label className="lt-field">
        <span>Observação (opcional) <InfoHint text="Contexto livre sobre o gap — não entra no cálculo de severidade." /></span>
        <textarea
          value={severityNote}
          onChange={e => setSeverityNote(e.target.value)}
          onBlur={() => save({ scopeNote, criticality, severityNote })}
        />
      </label>
      <span className={`lt-badge lt-badge--severity-${row.severityBand}`}>
        Severidade: {SEVERITY_LABEL[row.severityBand]}
      </span>
      {saveError && <p className="lt-alert" role="alert">{saveError}</p>}
    </div>
  )
}

function AccountHealthPanel({ row, repId, onRenewalDateUpdated }: { row: OpportunityRow; repId: string; onRenewalDateUpdated: () => void }) {
  const [renewalDate, setRenewalDate] = useState(toDateInputValue(row.renewalDate))
  const [saveError, setSaveError] = useState<string | null>(null)
  const requestSeq = useRef(0)

  const save = async (value: string) => {
    setSaveError(null)
    const seq = ++requestSeq.current
    try {
      await updateCompanyRenewalDate(row.companyId, value || null, repId.trim() || null)
      if (seq !== requestSeq.current) return
      onRenewalDateUpdated()
    } catch (err) {
      if (seq !== requestSeq.current) return
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar a data de renovação.')
    }
  }

  // .lt-panel-row (align-items: center) só pro badge+hint, que têm alturas
  // parecidas; o campo de data (label de duas linhas: texto + input) fica
  // numa linha própria abaixo — achado da auditoria de UI: os três num só
  // .lt-severity com align-items:flex-end só alinhava os RODAPÉS dos itens,
  // deixando os topos desencontrados em até 24px.
  return (
    <div className="lt-panel">
      <div className="lt-panel-row">
        <span className={`lt-badge lt-badge--health-${row.accountHealth}`}>
          Saúde da conta: {HEALTH_LABEL[row.accountHealth]}
        </span>
        <span className="lt-hint">
          Próxima revisão sugerida: {row.qbrSuggestedDays === 0 ? 'imediata' : `em ${row.qbrSuggestedDays} dias`}
          {' '}({QBR_REASON_LABEL[row.qbrReason] ?? row.qbrReason})
        </span>
      </div>
      <label className="lt-field">
        <span>Data de renovação do contrato <InfoHint text="Alimenta a cadência de revisão de conta (QBR) sugerida acima." /></span>
        <input
          type="date"
          value={renewalDate}
          onChange={e => setRenewalDate(e.target.value)}
          onBlur={() => save(renewalDate)}
        />
      </label>
      {saveError && <p className="lt-alert" role="alert">{saveError}</p>}
    </div>
  )
}

// Fase G, módulo 7 — frase por categoria (Sales Engineer consultado): canal +
// motivo em uma cláusula concreta, nunca o nome técnico da categoria. O canal
// já está embutido no verbo da frase (Ligar/Enviar e-mail/Mandar mensagem) —
// tem que bater com o `channel` real de `_CUSTOMER_CADENCE`/`_PROSPECT_CADENCE`
// (core/opportunity_engine.py), não com a suposição do agente consultado
// (achado de verificação ao vivo: a frase original dizia "ligar" pra
// continuidade_uso_atual, que na verdade é canal e-mail, e "enviar e-mail"
// pra gap_portfolio, que na verdade é canal ligação — texto contradizia a
// ação real, o rep leria "e-mail" e copiaria um texto pra usar numa ligação).
export const CADENCE_REASON_PHRASE: Record<string, (row: OpportunityRow) => string> = {
  continuidade_uso_atual: row =>
    `Enviar e-mail perguntando como está o uso de ${row.product ?? row.service ?? 'seus produtos atuais'} — é hora de reforçar o relacionamento.`,
  gap_portfolio: row =>
    `Ligar apresentando ${row.product ?? row.service ?? 'a solução recomendada'} — cliente já usa produtos relacionados mas não tem isso.`,
  prova_social_urgencia: () =>
    'Mandar mensagem no LinkedIn com um caso parecido — bom momento pra criar urgência.',
  abertura_sinal: () =>
    'Primeiro contato por e-mail — sinal identificado aponta interesse.',
  reforco_angulo_novo: () =>
    'Ligar com um ângulo diferente — a primeira abordagem não avançou, vale tentar outro gancho.',
}

// Fase H, módulo 4 (Sales Engineer consultado) — título de convite, nunca
// alarme; frase muda conforme os motivos presentes (nunca concatena as
// duas, senão vira uma lista burocrática em vez de uma síntese).
function threadingRiskPhrase(reasons: NextSuggestedTouch['threadingRiskReasons']): string {
  const hasSingleThread = reasons.includes('single_threaded_risk')
  const hasNoDecisor = reasons.includes('no_economic_buyer_contact')
  if (hasSingleThread && hasNoDecisor) {
    return 'Os toques recentes chegaram a uma pessoa só, e não a um decisor. Bom momento pra ampliar quem participa da conversa.'
  }
  if (hasSingleThread) {
    return 'Só um contato ativo tem recebido seus toques recentes. Vale envolver mais uma pessoa da conta.'
  }
  return 'Nenhum decisor apareceu nos toques recentes. Vale trazer quem decide pra conversa.'
}

type SuggestionCache = Map<string, NextSuggestedTouch>
type ContactsCache = Map<string, CompanyContact[]>

function NextActionSuggestion({ row, repId, suggestionCache, contactsCache }: {
  row: OpportunityRow
  repId: string
  suggestionCache: RefObject<SuggestionCache>
  contactsCache: RefObject<ContactsCache>
}) {
  const [suggestion, setSuggestion] = useState<NextSuggestedTouch | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  // idle -> botão "Copiar"; copied -> feedback "Copiado ✓" por 1,2s; ready -> botão "Marcar como enviado"
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'ready'>('idle')
  const [copying, setCopying] = useState(false)
  const [marking, setMarking] = useState(false)
  const [contacts, setContacts] = useState<CompanyContact[]>([])
  const [selectedContactId, setSelectedContactId] = useState<string | null>(null)
  // Fase L: depois de um 422 por "não contatar", o rep pode confirmar que o contato realmente aconteceu.
  const [acknowledgeBlock, setAcknowledgeBlock] = useState(false)
  const [blockedNotice, setBlockedNotice] = useState<string | null>(null)

  const cacheKey = `${row.id}:${repId}`

  const applySuggestion = (s: NextSuggestedTouch) => {
    setSuggestion(s)
    setCopyState('idle')
    setSelectedContactId(s.lastContactId)
  }

  // Achado da auditoria de performance: recolher e reabrir a MESMA linha
  // remontava o componente e refazia as duas chamadas de rede do zero —
  // cache por linha (sobrevive ao expand/collapse, só reseta ao trocar de
  // aba) evita isso. `forceRefresh` ignora o cache — usado só depois de
  // `markSent`, quando o dado realmente mudou no servidor.
  const load = (forceRefresh = false) => {
    if (!forceRefresh && suggestionCache.current?.has(cacheKey)) {
      applySuggestion(suggestionCache.current.get(cacheKey)!)
      return Promise.resolve()
    }
    return getNextSuggestedTouch(row.id, repId).then(s => {
      suggestionCache.current?.set(cacheKey, s)
      applySuggestion(s)
    })
  }

  useEffect(() => {
    setLoadError(null)
    load().catch(err => setLoadError(err instanceof Error ? err.message : 'Falha ao calcular a próxima ação.'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [row.id, repId])

  useEffect(() => {
    const cached = contactsCache.current?.get(row.companyId)
    if (cached) {
      setContacts(cached)
      return
    }
    // Dropdown é opcional/best-effort — falha aqui nunca deve virar erro
    // bloqueante (o rep ainda consegue copiar/marcar como enviado sem
    // atribuir contato nenhum), então some silenciosamente pra lista vazia.
    getCompanyContacts(row.companyId)
      .then(cs => { contactsCache.current?.set(row.companyId, cs); setContacts(cs) })
      .catch(() => setContacts([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [row.companyId])

  if (!repId.trim()) {
    return <p className="lt-hint">Informe seu id de representante acima para ver a próxima ação sugerida.</p>
  }
  if (loadError) return <p className="lt-alert" role="alert">{loadError}</p>
  if (!suggestion) return <p className="lt-hint">Calculando próxima ação…</p>

  // Fase G, módulo 8 (Sales Coach consultado) — sinal independente do
  // `state` da cadência: soma um alerta, nunca substitui a sugestão de
  // toque. Framing de decisão, nunca de fracasso.
  const silenceBanner = suggestion.silenceReason && (
    <p className="lt-advisory" role="alert">
      {suggestion.silenceReason === 'nunca_contatado'
        ? `Esta oportunidade está em qualificação há ${suggestion.silenceDays} dias sem nenhum contato registrado. Ainda faz sentido priorizá-la agora?`
        : `A cadência sugerida terminou há ${suggestion.silenceDays} dias sem retorno do lead. Bom momento pra decidir: tentar outro ângulo, escalar, ou dispensar.`}
    </p>
  )

  // Fase H, módulo 4 — independente de tudo acima, mesmo espírito do
  // silenceBanner: soma um alerta, nunca substitui a sugestão de toque.
  // .lt-panel (não .lt-severity): é um bloco de texto empilhado
  // (título + parágrafo), não uma linha de campos de formulário — achado
  // da auditoria de UI, .lt-severity é `flex-direction: row` e colocava os
  // dois lado a lado.
  const threadingBanner = suggestion.threadingRiskReasons.length > 0 && (
    <div className="lt-panel">
      <strong>Vale ampliar os contatos aqui</strong>
      <p className="lt-advisory">{threadingRiskPhrase(suggestion.threadingRiskReasons)}</p>
    </div>
  )

  if (suggestion.state === 'bloqueado') {
    return (
      <p className="lt-advisory" role="alert">
        Esta empresa está marcada como "não contatar" ({suggestion.blockReason ?? 'sem motivo informado'}), então não há
        próxima ação sugerida. Se a situação mudou, reative na seção "Não contatar" abaixo.
      </p>
    )
  }
  if (suggestion.state === 'aguardando_intervalo') {
    return (
      <>
        {silenceBanner}
        {threadingBanner}
        <p className="lt-hint">Sem ação sugerida agora — dentro do intervalo da cadência.</p>
      </>
    )
  }
  if (suggestion.state === 'cadencia_esgotada') {
    return (
      <>
        {silenceBanner}
        {threadingBanner}
        <p className="lt-hint">Sem retorno até agora — decida o próximo passo no status acima (encerrar ou continuar manualmente).</p>
      </>
    )
  }
  if (suggestion.state === 'cap_diario_atingido') {
    // ponytail: mensagem por linha, não o banner único agregado que o Sales
    // Engineer recomendou — ainda não existe uma lista agregada de ações do
    // dia por rep; upgrade quando essa superfície existir.
    return (
      <>
        {silenceBanner}
        {threadingBanner}
        <p className="lt-hint">Você atingiu o limite de contatos de hoje. Essa sugestão volta amanhã.</p>
      </>
    )
  }

  const phrase = CADENCE_REASON_PHRASE[suggestion.reasonCategory ?? '']?.(row) ?? 'Próxima ação sugerida.'
  const channel = suggestion.channel ?? 'email'

  const copy = async () => {
    setLoadError(null)
    setCopying(true)
    try {
      if (channel === 'email') {
        const draft = await generateEmailDraft(row, selectedContactId)
        await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.greeting}\n\n${draft.body}\n\n${draft.cta}`)
      } else {
        await navigator.clipboard.writeText(phrase)
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Falha ao copiar o conteúdo do contato.')
      setCopying(false)
      return
    }
    setCopying(false)
    setCopyState('copied')
    setTimeout(() => setCopyState('ready'), 1200)
  }

  const markSent = async () => {
    setMarking(true)
    try {
      await markOutreachTouchSent(row.id, repId, channel, phrase, selectedContactId, acknowledgeBlock)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Falha ao registrar o contato.'
      if (message.includes('não contatar')) {
        setBlockedNotice(message)
        setAcknowledgeBlock(true)
      } else {
        setLoadError(message)
      }
      setMarking(false)
      return
    }
    setBlockedNotice(null)
    setAcknowledgeBlock(false)
    try {
      await load(true)
    } catch {
      // Contato já foi gravado no servidor (POST acima teve sucesso) — só a
      // releitura da sugestão falhou, nunca reusar a mensagem de "falha ao
      // registrar" aqui, senão o rep acha que precisa registrar de novo.
      setLoadError('Contato registrado, mas não consegui atualizar a sugestão — recarregue a página.')
    } finally {
      setMarking(false)
    }
  }

  // .lt-panel (coluna) por fora — a frase fica em linha própria, de largura
  // cheia; .lt-panel-row (linha) só pro grupo pequeno de controles
  // (dropdown de contato + botão) — achado da auditoria de UI: misturar
  // texto de largura variável com controles pequenos numa única linha
  // flex-wrap produzia sobreposição/ordem imprevisível.
  return (
    <div className="lt-panel">
      {silenceBanner}
      {threadingBanner}
      {suggestion.lastContactBlocked && (
        <p className="lt-advisory" role="alert">O último contato registrado está marcado como "não contatar". Escolha outro contato antes de seguir.</p>
      )}
      {blockedNotice && (
        <p className="lt-alert" role="alert">
          {blockedNotice} Clique em "Registrar mesmo assim" só se o contato realmente aconteceu.
        </p>
      )}
      <p className="lt-panel-text">{phrase}</p>
      <div className="lt-panel-row">
        <label className="lt-field">
          <span>Contato (opcional) <InfoHint text="Pra quem o rascunho de e-mail abaixo é endereçado." /></span>
          <select value={selectedContactId ?? ''} onChange={e => setSelectedContactId(e.target.value || null)}>
            <option value="">Não atribuído</option>
            {contacts.map(c => <option key={c.id} value={c.id}>{c.name}{c.do_not_contact ? ' (não contatar)' : ''}</option>)}
          </select>
        </label>
        {copyState === 'idle' && (
          <button type="button" className="lt-btn" onClick={copy} disabled={copying}>
            {copying ? 'Copiando…' : channel === 'email' ? 'Copiar rascunho' : 'Copiar sugestão'}
          </button>
        )}
        {copyState === 'copied' && <span className="lt-hint">Copiado ✓</span>}
        {copyState === 'ready' && (
          <button type="button" className="lt-btn" onClick={markSent} disabled={marking}>
            {marking ? 'Registrando…' : acknowledgeBlock ? 'Registrar mesmo assim' : 'Marcar como enviado'}
          </button>
        )}
      </div>
    </div>
  )
}

// Rótulos de negócio (nunca o nome do campo) e formatação dos valores do histórico.
const AUDIT_FIELD_LABEL: Record<string, string> = {
  scope_note: 'Alcance do gap', criticality: 'Criticidade', severity_note: 'Observação de severidade',
  root_cause_stated: 'Por que isso acontece hoje?', trigger_event: 'Por que agora?',
  champion_stake: 'O que o contato ganha ou perde', discovery_skipped: 'Qualificada sem discovery',
  discovery_skip_reason: 'Justificativa para qualificar sem discovery', renewal_date: 'Data de renovação',
  industry: 'Setor', deal_size_hint: 'Porte estimado', stance: 'Postura do contato',
}

function auditValue(field: string, value: string | null): string {
  if (value === null) return 'vazio'
  if (field === 'renewal_date') return new Date(value).toLocaleDateString('pt-BR', { timeZone: 'UTC' })
  if (field === 'scope_note') return SCOPE_OPTIONS.find(o => o.value === value)?.label.split(' (')[0] ?? value
  if (field === 'criticality') return CRITICALITY_OPTIONS.find(o => o.value === value)?.label.split(' (')[0] ?? value
  if (field === 'discovery_skipped') return value === 'True' ? 'sim' : 'não'
  return value
}

function AuditHistory({ row }: { row: OpportunityRow }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    listOpportunityAudit(row.id).then(setEntries).catch(err => setError(err instanceof Error ? err.message : 'Falha ao carregar o histórico.'))
  }, [open, row.id])

  return (
    <div className="lt-panel">
      <button type="button" className="lt-btn" onClick={() => setOpen(v => !v)} aria-expanded={open}>
        {open ? 'Ocultar' : 'Ver'} histórico de alterações
      </button>
      {open && error && <p className="lt-alert" role="alert">{error}</p>}
      {open && entries !== null && entries.length === 0 && <p className="lt-hint">Nenhuma alteração registrada ainda.</p>}
      {open && entries !== null && entries.length > 0 && (
        <ul className="lt-hint">
          {entries.map(e => (
            <li key={e.id}>
              {new Date(e.changed_at).toLocaleString('pt-BR')} — {AUDIT_FIELD_LABEL[e.field] ?? e.field}: {auditValue(e.field, e.old_value)} → {auditValue(e.field, e.new_value)}
              {' '}({e.actor === 'sync' ? 'sincronização automática' : e.actor ?? 'não identificado'})
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const DNC_REASON_OPTIONS: { value: DoNotContactReason; label: string }[] = [
  { value: 'requested_by_contact', label: 'O contato pediu para não ser contatado' },
  { value: 'invalid_contact_data', label: 'Dados de contato inválidos' },
  { value: 'rep_decision', label: 'Decisão do representante' },
  { value: 'other', label: 'Outro motivo' },
]

function DoNotContactPanel({ row, repId }: { row: OpportunityRow; repId: string }) {
  const [entries, setEntries] = useState<DoNotContactEntry[]>([])
  const [contacts, setContacts] = useState<CompanyContact[]>([])
  const [contactId, setContactId] = useState('')
  const [channel, setChannel] = useState('')
  const [reason, setReason] = useState<DoNotContactReason>('requested_by_contact')
  const [comment, setComment] = useState('')
  const [liftingId, setLiftingId] = useState<string | null>(null)
  const [liftReason, setLiftReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const reload = () => listDoNotContact(row.companyId).then(setEntries)

  useEffect(() => {
    reload().catch(err => setError(err instanceof Error ? err.message : 'Falha ao carregar a lista de não contatar.'))
    getCompanyContacts(row.companyId).then(setContacts).catch(() => setContacts([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [row.companyId])

  const add = async () => {
    setError(null)
    try {
      await createDoNotContact(row.companyId, {
        repId, contactId: contactId || null, channel: channel || null, reason, comment,
      })
      setComment('')
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao marcar como não contatar.')
    }
  }

  const lift = async (id: string) => {
    setError(null)
    try {
      await liftDoNotContact(id, repId, liftReason)
      setLiftingId(null)
      setLiftReason('')
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao reativar.')
    }
  }

  const nameOf = (id: string | null) => (id ? contacts.find(c => c.id === id)?.name ?? 'Contato' : 'Empresa inteira')
  const active = entries.filter(e => !e.lifted_at)

  return (
    <div className="lt-panel">
      <strong>Não contatar</strong>
      {!repId.trim() && <p className="lt-hint">Informe seu id de representante acima para marcar ou reativar.</p>}
      {active.length === 0 && <p className="lt-hint">Nenhum bloqueio ativo nesta empresa.</p>}
      {active.map(e => (
        <div key={e.id} className="lt-panel-row">
          <span className="lt-panel-text">
            {nameOf(e.contact_id)} · {e.channel ?? 'todos os canais'} · {DNC_REASON_OPTIONS.find(o => o.value === e.reason)?.label}
            {e.comment ? ` — ${e.comment}` : ''}
          </span>
          {liftingId === e.id ? (
            <>
              <label className="lt-field">
                <span>Por que reativar? (opcional)</span>
                <input value={liftReason} onChange={ev => setLiftReason(ev.target.value)} maxLength={500} />
              </label>
              <button type="button" className="lt-btn" onClick={() => lift(e.id)} disabled={!repId.trim()}>Confirmar reativação</button>
            </>
          ) : (
            <button type="button" className="lt-btn" onClick={() => setLiftingId(e.id)}>Reativar</button>
          )}
        </div>
      ))}
      <div className="lt-panel-row">
        <label className="lt-field">
          <span>Quem</span>
          <select value={contactId} onChange={e => setContactId(e.target.value)}>
            <option value="">Empresa inteira</option>
            {contacts.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="lt-field">
          <span>Canal</span>
          <select value={channel} onChange={e => setChannel(e.target.value)}>
            <option value="">Todos os canais</option>
            <option value="email">E-mail</option>
            <option value="ligação">Ligação</option>
            <option value="linkedin">LinkedIn</option>
          </select>
        </label>
        <label className="lt-field">
          <span>Motivo</span>
          <select value={reason} onChange={e => setReason(e.target.value as DoNotContactReason)}>
            {DNC_REASON_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <label className="lt-field">
          <span>Observação (opcional) <InfoHint text="Fica só aqui: não vai para exportações nem para a IA." /></span>
          <input value={comment} onChange={e => setComment(e.target.value)} maxLength={500} />
        </label>
        <button type="button" className="lt-btn" onClick={add} disabled={!repId.trim()}>Marcar como não contatar</button>
      </div>
      {error && <p className="lt-alert" role="alert">{error}</p>}
    </div>
  )
}

function RowDetail({ row, repId, onRowUpdated, onRenewalDateUpdated, suggestionCache, contactsCache, aiHasKey }: {
  row: OpportunityRow
  repId: string
  onRowUpdated: (updated: OpportunityRow) => void
  onRenewalDateUpdated: () => void
  suggestionCache: RefObject<SuggestionCache>
  contactsCache: RefObject<ContactsCache>
  aiHasKey: boolean
}) {
  const [bcState, setBcState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [bcError, setBcError] = useState<string | null>(null)
  const [bcMessage, setBcMessage] = useState<string | null>(null)
  const [bcUseAi, setBcUseAi] = useState(false)
  const bcCheck = canExportBusinessCase(row)
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

  const handleExportBusinessCase = async () => {
    if (!bcCheck.enabled || bcState === 'loading') return
    const usarIa = aiHasKey && bcUseAi
    setBcState('loading')
    setBcError(null)
    setBcMessage(null)
    try {
      const { fonte } = await exportBusinessCase(row.id, usarIa, row.companyName)
      setBcMessage(proseSourceMessage(fonte, usarIa))
      setBcState('idle')
    } catch (err) {
      setBcError(err instanceof Error ? err.message : 'Falha ao gerar o business case.')
      setBcState('error')
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
          {safeHttpUrl(row.companyWebsite) && (
            <>
              <dt>Site</dt>
              <dd><a href={safeHttpUrl(row.companyWebsite) as string} target="_blank" rel="noopener noreferrer">{websiteLabel(row.companyWebsite as string)}</a></dd>
            </>
          )}
          {row.discoveryPrompt && (<><dt>Pergunta para o cliente</dt><dd>{row.discoveryPrompt}</dd></>)}
        </dl>
        <DiscoveryFields row={row} repId={repId} onUpdated={onRowUpdated} />
        <DoNotContactPanel row={row} repId={repId} />
        <StatusTransition row={row} onUpdated={onRowUpdated} />
        <AccountHealthPanel row={row} repId={repId} onRenewalDateUpdated={onRenewalDateUpdated} />
        <SeverityQualification row={row} repId={repId} onUpdated={onRowUpdated} />
        <AuditHistory row={row} />
        <div className="lt-panel">
          <strong>Próxima ação sugerida</strong>
          <NextActionSuggestion row={row} repId={repId} suggestionCache={suggestionCache} contactsCache={contactsCache} />
        </div>
        <div className="lt-detail-actions">
          <button type="button" className="lt-btn" onClick={copySummary}>Copiar resumo</button>
          <button type="button" className="lt-btn" onClick={handleGenerateDraft} disabled={draftState === 'loading'}>
            {draftState === 'loading' ? 'Gerando…' : 'Gerar rascunho'}
          </button>
          <button
            type="button" className="lt-btn" onClick={handleExportBusinessCase}
            aria-disabled={!bcCheck.enabled || bcState === 'loading'} aria-busy={bcState === 'loading'}
            aria-describedby={bcCheck.enabled ? undefined : `bc-reason-${row.id}`}
          >
            {bcState === 'loading' ? 'Gerando business case…' : 'Exportar business case'}
          </button>
          <label>
            <input
              type="checkbox" checked={aiHasKey && bcUseAi} disabled={!aiHasKey}
              onChange={e => { setBcUseAi(e.target.checked); setBcMessage(null); setBcError(null); setBcState('idle') }}
            />{' '}Melhorar o texto com IA
          </label>
          <InfoHint text="Envia os dados desta oportunidade (empresa, evidências, produto) ao provedor de IA configurado para reescrever o texto. Sem isso, usamos o texto padrão. Os números nunca são alterados." />
        </div>
        {!bcCheck.enabled && <p className="lt-hint" id={`bc-reason-${row.id}`}>{bcCheck.reason}</p>}
        {!aiHasKey && <p className="lt-hint">Configure a IA em Configurações</p>}
        {bcState === 'error' && <p className="lt-alert" role="alert">{bcError}</p>}
        {draftState === 'error' && <p className="lt-alert" role="alert">{draftError}</p>}
        <div role="status">
        {bcMessage && <p className="lt-hint">{bcMessage}</p>}
        {draft && (
          <div className="lt-draft">
            <p><strong>Assunto:</strong> {draft.subject}</p>
            <p>{draft.greeting}</p>
            <p>{draft.body}</p>
            <p>{draft.cta}</p>
            <button type="button" className="lt-btn" onClick={copyDraft}>Copiar rascunho</button>
            <p className="lt-hint">Revise antes de enviar — o rascunho nunca é enviado automaticamente.</p>
          </div>
        )}
        </div>
      </td>
    </tr>
  )
}

export function OpportunityTable({ rows, repId, onRowUpdated, onRenewalDateUpdated }: {
  rows: OpportunityRow[]
  repId: string
  onRowUpdated: (updated: OpportunityRow) => void
  onRenewalDateUpdated: () => void
}) {
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  // Vive aqui (não em NextActionSuggestion) porque OpportunityTable nunca
  // desmonta ao expandir/recolher linha — sobrevive ao ciclo que causava o
  // refetch desnecessário (achado da auditoria de performance).
  const suggestionCache = useRef<SuggestionCache>(new Map())
  const contactsCache = useRef<ContactsCache>(new Map())
  // Carregado uma vez; falha = sem IA (checkbox desabilitado).
  const [aiHasKey, setAiHasKey] = useState(false)
  useEffect(() => {
    getAiConfig().then(c => setAiHasKey(c.has_key)).catch(() => setAiHasKey(false))
  }, [])

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setDirection(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setDirection('desc')
    }
  }

  // Achado da auditoria de performance: sortRows rodava a cada render (ex.
  // ao expandir/recolher linha), não só quando dado/ordenação mudavam.
  const sorted = useMemo(() => sortRows(rows, sortKey, direction), [rows, sortKey, direction])

  if (rows.length === 0) {
    return <p className="lt-empty" role="status">Nenhuma oportunidade encontrada com os filtros atuais.</p>
  }

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
              <RowDetail
                row={row} repId={repId} onRowUpdated={onRowUpdated} onRenewalDateUpdated={onRenewalDateUpdated}
                suggestionCache={suggestionCache} contactsCache={contactsCache} aiHasKey={aiHasKey}
              />
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}
