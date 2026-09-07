import { useEffect, useState, type KeyboardEvent } from 'react'
import { exportOpportunitiesExcel, exportOpportunitiesPdf, listOpportunities } from './api'
import { Dashboard } from './dashboard/Dashboard'
import { applyFilters, defaultFilters, Filters, summarizeFilters, type FilterState } from './Filters'
import { GeoDiscoveryWizard } from './GeoDiscoveryWizard'
import { OpportunityTable } from './OpportunityTable'
import { SettingsScreen } from './settings/SettingsScreen'
import { styles } from './styles'
import type { OpportunityRow } from './types'

type Tab = 'dashboard' | 'oportunidades' | 'prospeccao' | 'configuracoes'

function OpportunitiesView() {
  const [rows, setRows] = useState<OpportunityRow[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FilterState>(defaultFilters)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null)
  // Fase G, módulo 7 — id do representante usado nas sugestões de próxima
  // ação (cota diária/cadência são por rep). Persistido em localStorage
  // porque o módulo não tem conceito de usuário logado ainda.
  const [repId, setRepId] = useState(() => localStorage.getItem('lt_rep_id') ?? '')

  const handleRepIdChange = (value: string) => {
    setRepId(value)
    localStorage.setItem('lt_rep_id', value)
  }

  const reload = () => {
    listOpportunities()
      .then(setRows)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Não consegui carregar as oportunidades.'))
  }

  useEffect(reload, [])

  const filtered = rows ? applyFilters(rows, filters) : []

  const handleRowUpdated = (updated: OpportunityRow) => {
    setRows(prev => prev && prev.map(r => (r.id === updated.id ? updated : r)))
  }

  // renewal_date fica em Company, não em Opportunity — a rota que grava não
  // devolve o OpportunityOut recalculado (account_health/qbr dependem de
  // toda a conta), então recarrega a lista inteira em vez de tentar
  // recalcular a saúde da conta no frontend.
  const handleRenewalDateUpdated = () => reload()

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

  if (loadError) return <p className="lt-alert" role="alert">{loadError}</p>
  if (!rows) return <p className="lt-hint">Carregando oportunidades…</p>

  return (
    <div>
      <div className="lt-header">
        <h2>Oportunidades</h2>
        <p>Lead.Tracker · {filtered.length} de {rows.length} oportunidades</p>
      </div>
      <div className="lt-toolbar">
        <label>
          Seu id de representante
          <input value={repId} onChange={e => handleRepIdChange(e.target.value)} placeholder="Id ou nome do representante" />
        </label>
        <button type="button" className="lt-btn" onClick={() => handleExport('pdf')} disabled={exporting !== null} aria-busy={exporting === 'pdf'}>
          {exporting === 'pdf' ? 'Gerando PDF…' : 'PDF'}
        </button>
        <button type="button" className="lt-btn" onClick={() => handleExport('excel')} disabled={exporting !== null} aria-busy={exporting === 'excel'}>
          {exporting === 'excel' ? 'Gerando Excel…' : 'Excel'}
        </button>
      </div>
      {exportError && <p className="lt-alert" role="alert">{exportError}</p>}
      <Filters rows={rows} value={filters} onChange={setFilters} />
      {rows.length === 0 ? (
        <p className="lt-empty" role="status">
          Nenhuma oportunidade ainda — rode uma sincronização em Configurações.
        </p>
      ) : (
        <OpportunityTable
          rows={filtered}
          repId={repId}
          onRowUpdated={handleRowUpdated}
          onRenewalDateUpdated={handleRenewalDateUpdated}
        />
      )}
    </div>
  )
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'oportunidades', label: 'Oportunidades' },
  { id: 'prospeccao', label: 'Prospecção' },
  { id: 'configuracoes', label: 'Configurações' },
]

export function App() {
  const [tab, setTab] = useState<Tab>('dashboard')

  // Achado da auditoria de acessibilidade: tabs sem navegação por seta
  // obrigam quem usa teclado/leitor de tela a tabular por todos os
  // outros controles da página pra trocar de aba. Roving tabindex
  // padrão do padrão ARIA tabs: só a aba ativa é alcançável por Tab; as
  // setas movem o foco (e a seleção) entre as abas.
  const handleTabKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null
    if (e.key === 'ArrowRight') nextIndex = (index + 1) % TABS.length
    else if (e.key === 'ArrowLeft') nextIndex = (index - 1 + TABS.length) % TABS.length
    else if (e.key === 'Home') nextIndex = 0
    else if (e.key === 'End') nextIndex = TABS.length - 1
    if (nextIndex === null) return
    e.preventDefault()
    setTab(TABS[nextIndex].id)
    const nextButton = e.currentTarget.parentElement?.children[nextIndex] as HTMLElement | undefined
    nextButton?.focus()
  }

  return (
    <div className="lt-root">
      <style>{styles}</style>
      <div className="lt-tabs" role="tablist" aria-label="Navegação Lead.Tracker">
        {TABS.map((t, index) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`lt-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`lt-tabpanel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            className="lt-tab"
            onClick={() => setTab(t.id)}
            onKeyDown={e => handleTabKeyDown(e, index)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {TABS.map(t => (
        <div
          key={t.id}
          role="tabpanel"
          id={`lt-tabpanel-${t.id}`}
          aria-labelledby={`lt-tab-${t.id}`}
          hidden={tab !== t.id}
        >
          {tab === t.id && (
            <>
              {t.id === 'dashboard' && <Dashboard />}
              {t.id === 'oportunidades' && <OpportunitiesView />}
              {t.id === 'prospeccao' && <GeoDiscoveryWizard />}
              {t.id === 'configuracoes' && <SettingsScreen />}
            </>
          )}
        </div>
      ))}
    </div>
  )
}
