import { useEffect, useState } from 'react'
import { exportOpportunitiesExcel, exportOpportunitiesPdf, listOpportunities } from './api'
import { Dashboard } from './dashboard/Dashboard'
import { applyFilters, defaultFilters, Filters, summarizeFilters, type FilterState } from './Filters'
import { OpportunityTable } from './OpportunityTable'
import { SettingsScreen } from './settings/SettingsScreen'
import { styles } from './styles'
import type { OpportunityRow } from './types'

type Tab = 'dashboard' | 'oportunidades' | 'configuracoes'

function OpportunitiesView() {
  const [rows, setRows] = useState<OpportunityRow[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FilterState>(defaultFilters)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null)

  useEffect(() => {
    listOpportunities()
      .then(setRows)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Não consegui carregar as oportunidades.'))
  }, [])

  const filtered = rows ? applyFilters(rows, filters) : []

  const handleQualificationUpdated = (updated: OpportunityRow) => {
    setRows(prev => prev && prev.map(r => (r.id === updated.id ? updated : r)))
  }

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

  if (loadError) return <p className="lt-hint" role="alert">{loadError}</p>
  if (!rows) return <p className="lt-hint">Carregando oportunidades…</p>

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
      {rows.length === 0 ? (
        <p className="lt-empty" role="status">
          Nenhuma oportunidade ainda — rode uma sincronização em Configurações.
        </p>
      ) : (
        <OpportunityTable rows={filtered} onQualificationUpdated={handleQualificationUpdated} />
      )}
    </div>
  )
}

export function App() {
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
        <button type="button" role="tab" aria-selected={tab === 'configuracoes'} className="lt-tab" onClick={() => setTab('configuracoes')}>
          Configurações
        </button>
      </div>
      {tab === 'dashboard' && <Dashboard />}
      {tab === 'oportunidades' && <OpportunitiesView />}
      {tab === 'configuracoes' && <SettingsScreen />}
    </div>
  )
}
