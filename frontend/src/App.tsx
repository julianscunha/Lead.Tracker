import { useState } from 'react'
import { Dashboard } from './dashboard/Dashboard'
import { applyFilters, defaultFilters, Filters, type FilterState } from './Filters'
import { OpportunityTable } from './OpportunityTable'
import { sampleOpportunities } from './sampleData'
import { styles } from './styles'
import type { OpportunityRow } from './types'

type Tab = 'dashboard' | 'oportunidades'

function OpportunitiesView({ rows }: { rows: OpportunityRow[] }) {
  const [filters, setFilters] = useState<FilterState>(defaultFilters)
  const filtered = applyFilters(rows, filters)

  return (
    <div>
      <div className="lt-header">
        <h2>Oportunidades</h2>
        <p>Lead.Tracker · {filtered.length} de {rows.length} oportunidades</p>
      </div>
      <Filters rows={rows} value={filters} onChange={setFilters} />
      <OpportunityTable rows={filtered} />
    </div>
  )
}

export function App({ rows = sampleOpportunities }: { rows?: OpportunityRow[] }) {
  const [tab, setTab] = useState<Tab>('dashboard')

  return (
    <div className="lt-root">
      <style>{styles}</style>
      <div className="lt-tabs" role="tablist" aria-label="Navegação Lead.Tracker">
        <button type="button" role="tab" aria-selected={tab === 'dashboard'} className="lt-tab" onClick={() => setTab('dashboard')}>
          Dashboard
        </button>
        <button type="button" role="tab" aria-selected={tab === 'oportunidades'} className="lt-tab" onClick={() => setTab('oportunidades')}>
          Oportunidades
        </button>
      </div>
      {tab === 'dashboard' ? <Dashboard /> : <OpportunitiesView rows={rows} />}
    </div>
  )
}
