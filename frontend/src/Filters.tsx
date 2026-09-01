import type { ClientFilter, OpportunityRow } from './types'

export interface FilterState {
  client: ClientFilter
  product: string
  service: string
  source: string
  minScore: number
}

export const defaultFilters: FilterState = {
  client: 'todos', product: 'todos', service: 'todos', source: 'todos', minScore: 0,
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
      <label htmlFor="lt-filter-client">
        Cliente
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

      <label htmlFor="lt-filter-product">
        Produto
        <select id="lt-filter-product" value={value.product} onChange={e => onChange({ ...value, product: e.target.value })}>
          <option value="todos">Todos</option>
          {products.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>

      <label htmlFor="lt-filter-service">
        Serviço
        <select id="lt-filter-service" value={value.service} onChange={e => onChange({ ...value, service: e.target.value })}>
          <option value="todos">Todos</option>
          {services.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      <label htmlFor="lt-filter-source">
        Fonte
        <select id="lt-filter-source" value={value.source} onChange={e => onChange({ ...value, source: e.target.value })}>
          <option value="todos">Todas</option>
          {sources.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      <label htmlFor="lt-filter-score">
        Score mínimo
        <input
          id="lt-filter-score"
          type="number" min={0} max={1} step={0.1}
          value={value.minScore}
          onChange={e => onChange({ ...value, minScore: Number(e.target.value) })}
        />
      </label>
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
    return true
  })
}
