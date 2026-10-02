import type { AccountHealth, ClientFilter, OpportunityRow, OpportunityStatus } from './types'
import { InfoHint } from './InfoHint'

export interface FilterState {
  client: ClientFilter
  product: string
  service: string
  source: string
  minScore: number
  status: OpportunityStatus | 'todos'
  health: AccountHealth | 'todos'
  /** Só as detectadas há mais tempo que o SLA de triagem (vem do Dashboard: "Triagem atrasada"). */
  onlyAging: boolean
}

export const defaultFilters: FilterState = {
  client: 'todos', product: 'todos', service: 'todos', source: 'todos', minScore: 0,
  status: 'todos', health: 'todos', onlyAging: false,
}

export const STATUS_LABEL: Record<OpportunityStatus, string> = {
  detected: 'Detectada', qualified: 'Qualificada', reviewed: 'Revisada', contacted: 'Contatada',
  opportunity: 'Oportunidade', dismissed: 'Descartada',
}

export const HEALTH_LABEL: Record<AccountHealth, string> = {
  verde: 'Saudável', amarela: 'Atenção', vermelha: 'Crítica', dados_insuficientes: 'Dados insuficientes',
}

function uniqueSorted(values: (string | null)[]): string[] {
  return Array.from(new Set(values.filter((v): v is string => Boolean(v)))).sort()
}

export function Filters({
  rows, value, onChange,
}: {
  rows: OpportunityRow[]
  value: FilterState
  onChange: (next: FilterState) => void
}) {
  const products = uniqueSorted(rows.map(r => r.product))
  const services = uniqueSorted(rows.map(r => r.service))
  const sources = uniqueSorted(rows.flatMap(r => r.sources.map(s => s.type)))

  return (
    <div className="lt-filters" role="group" aria-label="Filtros de oportunidades">
      <label htmlFor="lt-filter-status" className="lt-field">
        <span>Status <InfoHint text="Etapa do funil: detectada, qualificada, revisada, contatada, oportunidade ou descartada." /></span>
        <select id="lt-filter-status" value={value.status} onChange={e => onChange({ ...value, status: e.target.value as FilterState['status'] })}>
          <option value="todos">Todos</option>
          {(Object.keys(STATUS_LABEL) as (keyof typeof STATUS_LABEL)[]).map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
      </label>

      <label htmlFor="lt-filter-health" className="lt-field">
        <span>Saúde da conta <InfoHint text="Situação da conta (renovação e atividade): saudável, atenção, crítica ou sem dados suficientes." /></span>
        <select id="lt-filter-health" value={value.health} onChange={e => onChange({ ...value, health: e.target.value as FilterState['health'] })}>
          <option value="todos">Todas</option>
          {(Object.keys(HEALTH_LABEL) as (keyof typeof HEALTH_LABEL)[]).map(h => <option key={h} value={h}>{HEALTH_LABEL[h]}</option>)}
        </select>
      </label>

      <label htmlFor="lt-filter-client" className="lt-field">
        <span>Cliente <InfoHint text="Filtra pela relação da empresa: cliente atual ou prospect ainda sem venda." /></span>
        <select
          id="lt-filter-client"
          value={value.client}
          onChange={e => onChange({ ...value, client: e.target.value as ClientFilter })}
        >
          <option value="todos">Todos</option>
          <option value="clientes">Clientes atuais</option>
          <option value="prospects">Prospects</option>
        </select>
      </label>

      <label htmlFor="lt-filter-product" className="lt-field">
        <span>Produto <InfoHint text="Mostra só oportunidades associadas a esse produto do portfólio." /></span>
        <select id="lt-filter-product" value={value.product} onChange={e => onChange({ ...value, product: e.target.value })}>
          <option value="todos">Todos</option>
          {products.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>

      <label htmlFor="lt-filter-service" className="lt-field">
        <span>Serviço <InfoHint text="Mostra só oportunidades associadas a esse serviço do portfólio." /></span>
        <select id="lt-filter-service" value={value.service} onChange={e => onChange({ ...value, service: e.target.value })}>
          <option value="todos">Todos</option>
          {services.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      <label htmlFor="lt-filter-source" className="lt-field">
        <span>Fonte <InfoHint text="Mostra só oportunidades com evidência vinda dessa fonte de dados." /></span>
        <select id="lt-filter-source" value={value.source} onChange={e => onChange({ ...value, source: e.target.value })}>
          <option value="todos">Todas</option>
          {sources.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      <label htmlFor="lt-filter-score" className="lt-field">
        <span>Score mínimo <InfoHint text="De 0.0 a 1.0 — esconde oportunidades com aderência abaixo desse valor." /></span>
        <input
          id="lt-filter-score"
          type="number" min={0} max={1} step={0.1}
          value={value.minScore}
          onChange={e => onChange({ ...value, minScore: Number(e.target.value) })}
        />
      </label>

      {value.onlyAging && (
        <button type="button" className="lt-btn" onClick={() => onChange({ ...value, onlyAging: false })}
          aria-label="Remover o filtro de triagem atrasada">
          Triagem atrasada ✕
        </button>
      )}
    </div>
  )
}

export function summarizeFilters(filters: FilterState): string {
  const parts: string[] = []
  if (filters.client !== 'todos') parts.push(filters.client === 'clientes' ? 'clientes atuais' : 'prospects')
  if (filters.product !== 'todos') parts.push(`produto: ${filters.product}`)
  if (filters.service !== 'todos') parts.push(`serviço: ${filters.service}`)
  if (filters.source !== 'todos') parts.push(`fonte: ${filters.source}`)
  if (filters.minScore > 0) parts.push(`score mínimo: ${filters.minScore}`)
  if (filters.status !== 'todos') parts.push(`status: ${STATUS_LABEL[filters.status].toLowerCase()}`)
  if (filters.health !== 'todos') parts.push(`saúde da conta: ${HEALTH_LABEL[filters.health].toLowerCase()}`)
  if (filters.onlyAging) parts.push('triagem atrasada')
  return parts.length > 0 ? parts.join(', ') : 'sem filtro'
}

export function applyFilters(rows: OpportunityRow[], filters: FilterState): OpportunityRow[] {
  return rows.filter(r => {
    if (filters.client === 'clientes' && !r.isCustomer) return false
    if (filters.client === 'prospects' && r.isCustomer) return false
    if (filters.product !== 'todos' && r.product !== filters.product) return false
    if (filters.service !== 'todos' && r.service !== filters.service) return false
    if (filters.source !== 'todos' && !r.sources.some(s => s.type === filters.source)) return false
    if ((r.opportunityScore ?? 0) < filters.minScore) return false
    if (filters.status !== 'todos' && r.status !== filters.status) return false
    if (filters.health !== 'todos' && r.accountHealth !== filters.health) return false
    if (filters.onlyAging && !r.isAging) return false
    return true
  })
}
