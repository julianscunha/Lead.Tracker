import { useState } from 'react'
import { exportOpportunitiesExcel, exportOpportunitiesPdf } from './api'
import { Dashboard } from './dashboard/Dashboard'
import { applyFilters, defaultFilters, Filters, summarizeFilters, type FilterState } from './Filters'
import { OpportunityTable } from './OpportunityTable'
import { sampleOpportunities } from './sampleData'
import { styles } from './styles'
import type { OpportunityRow } from './types'

type Tab = 'dashboard' | 'oportunidades'

function OpportunitiesView({ rows }: { rows: OpportunityRow[] }) {
  const [filters, setFilters] = useState<FilterState>(defaultFilters)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null)
  const filtered = applyFilters(rows, filters)

  const handleExport = async (kind: 'pdf' | 'excel') => {
    setExportError(null)
    setExporting(kind)
    try {
      const summary = summarizeFilters(filters)
      if (kind === 'pdf') await exportOpportunitiesPdf(filtered, summary)
      else await exportOpportunitiesExcel(filtered)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Falha ao exportar.')
    } finally {
      setExporting(null)
    }
  }

  return (
    <div>
      <div className="lt-header">
        <h2>Oportunidades</h2>
        <p>Lead.Tracker · {filtered.length} de {rows.length} oportunidades</p>
      </div>
      <div className="lt-toolbar">
        <button type="button" className="lt-btn" onClick={() => handleExport('pdf')} disabled={exporting !== null} aria-busy={exporting === 'pdf'}>
          {exporting === 'pdf' ? 'Gerando PDF…' : 'PDF'}
        </button>
        <button type="button" className="lt-btn" onClick={() => handleExport('excel')} disabled={exporting !== null} aria-busy={exporting === 'excel'}>
          {exporting === 'excel' ? 'Gerando Excel…' : 'Excel'}
        </button>
      </div>
      {exportError && <p className="lt-hint" role="alert">{exportError}</p>}
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
