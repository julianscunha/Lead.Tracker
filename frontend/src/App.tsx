import { useState } from 'react'
import { applyFilters, defaultFilters, Filters, type FilterState } from './Filters'
import { OpportunityTable } from './OpportunityTable'
import { sampleOpportunities } from './sampleData'
import { styles } from './styles'
import type { OpportunityRow } from './types'

export function App({ rows = sampleOpportunities }: { rows?: OpportunityRow[] }) {
  const [filters, setFilters] = useState<FilterState>(defaultFilters)
  const filtered = applyFilters(rows, filters)

  return (
    <div className="lt-root">
      <style>{styles}</style>
      <div className="lt-header">
        <h2>Oportunidades</h2>
        <p>Lead.Tracker · {filtered.length} de {rows.length} oportunidades</p>
      </div>
      <Filters rows={rows} value={filters} onChange={setFilters} />
      <OpportunityTable rows={filtered} />
    </div>
  )
}
