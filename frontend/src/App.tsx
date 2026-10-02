import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { exportOpportunitiesExcel, exportOpportunitiesPdf, listOpportunities } from './api'
import { Dashboard } from './dashboard/Dashboard'
import { applyFilters, defaultFilters, Filters, summarizeFilters, type FilterState } from './Filters'
import { OpportunityTable } from './OpportunityTable'
import { useRepId } from './repId'
import { ConflictsSection } from './settings/ConflictsSection'
import { DataInputScreen } from './settings/DataInputScreen'
import { SettingsScreen } from './settings/SettingsScreen'
import { styles } from './styles'
import type { OpportunityRow } from './types'
import { InfoHint } from './InfoHint'

export type Tab = 'dashboard' | 'entrada' | 'oportunidades' | 'configuracoes'

// Ordem = fluxo de trabalho: ver (Dashboard) → alimentar (Entrada de dados) → lapidar e agir
// (Oportunidades, que também recebe a saída: exportar, rascunho, business case) → calibrar (Configurações).
const TABS: { id: Tab; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'entrada', label: 'Entrada de dados' },
  { id: 'oportunidades', label: 'Oportunidades' },
  { id: 'configuracoes', label: 'Configurações' },
]

function OpportunitiesView({ repId, initialFilters, onNavigate, active }: {
  repId: string
  initialFilters: FilterState
  onNavigate: (tab: Tab) => void
  active: boolean
}) {
  const [rows, setRows] = useState<OpportunityRow[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FilterState>(initialFilters)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null)

  const reload = () => {
    listOpportunities()
      .then(setRows)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Não consegui carregar as oportunidades.'))
  }

  useEffect(reload, [])
  // A aba fica montada ao trocar (não perde filtros nem linha aberta); ao voltar para ela a lista é atualizada.
  const wasActive = useRef(active)
  useEffect(() => {
    if (active && !wasActive.current) reload()
    wasActive.current = active
  }, [active])

  const filtered = rows ? applyFilters(rows, filters) : []

  const handleRowUpdated = (updated: OpportunityRow) => {
    setRows(prev => prev && prev.map(r => (r.id === updated.id ? updated : r)))
  }

  // renewal_date fica em Company, não em Opportunity — a rota que grava não devolve o OpportunityOut
  // recalculado (account_health/qbr dependem de toda a conta), então recarrega a lista inteira.
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
      <div className="lt-header lt-header-row">
        <div>
          <h2>Oportunidades</h2>
          <p>{filtered.length} de {rows.length} oportunidades</p>
        </div>
        <InfoHint text="Aqui você lapida e age: qualifica, preenche a discovery, resolve conflitos de dados, decide o próximo passo, gera rascunho ou business case e exporta o que está na tela." />
      </div>

      {/* Conflitos entre fontes: trabalho recorrente de lapidação; só aparece quando há algum. */}
      <ConflictsSection repId={repId} onResolved={reload} />

      <div className="lt-toolbar">
        <button type="button" className="lt-btn" onClick={() => handleExport('pdf')} disabled={exporting !== null} aria-busy={exporting === 'pdf'}>
          {exporting === 'pdf' ? 'Gerando PDF…' : 'Exportar PDF'}
        </button>
        <button type="button" className="lt-btn" onClick={() => handleExport('excel')} disabled={exporting !== null} aria-busy={exporting === 'excel'}>
          {exporting === 'excel' ? 'Gerando Excel…' : 'Exportar Excel'}
        </button>
      </div>
      {exportError && <p className="lt-alert" role="alert">{exportError}</p>}
      <Filters rows={rows} value={filters} onChange={setFilters} />
      {rows.length === 0 ? (
        <div className="lt-empty" role="status">
          <p>Nenhuma oportunidade ainda.</p>
          <button type="button" className="lt-btn" onClick={() => onNavigate('entrada')}>Trazer dados em Entrada de dados</button>
        </div>
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

export function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [visited, setVisited] = useState<Set<Tab>>(() => new Set<Tab>(['dashboard']))
  const [repId, setRepId] = useRepId()
  const rootRef = useRef<HTMLDivElement>(null)
  // Filtro aplicado ao entrar em Oportunidades vindo do Dashboard (ex.: "Triagem atrasada").
  // `key` força o remonte da lista para aplicar o filtro novo.
  const [pendingFilters, setPendingFilters] = useState<FilterState>(defaultFilters)
  const [filtersKey, setFiltersKey] = useState(0)

  const navigate = (next: Tab, filters?: Partial<FilterState>) => {
    // Só um ATALHO (com filtros, mesmo vazios) reinicia a lista; clicar na aba mantém filtros e linha aberta.
    if (next === 'oportunidades' && filters !== undefined) {
      setPendingFilters({ ...defaultFilters, ...(filters ?? {}) })
      setFiltersKey(k => k + 1)
    }
    setTab(next)
    setVisited(prev => (prev.has(next) ? prev : new Set(prev).add(next)))
    // Navegação por atalho (ex.: tile do Dashboard) desmonta o elemento focado: leva o foco para a aba nova.
    requestAnimationFrame(() => rootRef.current?.querySelector<HTMLElement>(`#lt-tab-${next}`)?.focus())
  }

  // Achado da auditoria de acessibilidade: tabs sem navegação por seta obrigam quem usa teclado/leitor de
  // tela a tabular por todos os outros controles. Roving tabindex do padrão ARIA tabs: só a aba ativa é
  // alcançável por Tab; as setas movem o foco (e a seleção) entre as abas.
  const handleTabKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null
    if (e.key === 'ArrowRight') nextIndex = (index + 1) % TABS.length
    else if (e.key === 'ArrowLeft') nextIndex = (index - 1 + TABS.length) % TABS.length
    else if (e.key === 'Home') nextIndex = 0
    else if (e.key === 'End') nextIndex = TABS.length - 1
    if (nextIndex === null) return
    e.preventDefault()
    navigate(TABS[nextIndex].id)
    const nextButton = e.currentTarget.parentElement?.children[nextIndex] as HTMLElement | undefined
    nextButton?.focus()
  }

  return (
    <div className="lt-root" ref={rootRef}>
      <style>{styles}</style>
      <div className="lt-topbar">
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
              onClick={() => navigate(t.id)}
              onKeyDown={e => handleTabKeyDown(e, index)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {/* Identidade digitada UMA vez e lembrada: usada na próxima ação, na prospecção, nos conflitos e no histórico. */}
        <div className="lt-who">
          <label htmlFor="lt-rep-id">Você é</label>
          <InfoHint text="Seu id ou nome de representante. Vale para todo o módulo: cota de contatos e próxima ação, prospecção, escolhas em conflitos de dados e o histórico de alterações. O produto ainda não tem login, então este nome não é verificado." />
          <input id="lt-rep-id" value={repId} onChange={e => setRepId(e.target.value)} placeholder="Id ou nome" maxLength={64} />
        </div>
      </div>
      {TABS.map(t => (
        <div
          key={t.id}
          role="tabpanel"
          id={`lt-tabpanel-${t.id}`}
          aria-labelledby={`lt-tab-${t.id}`}
          hidden={tab !== t.id}
        >
          {/* Monta na 1ª visita e MANTÉM montado: trocar de aba não perde filtros, linha aberta, rascunho nem o passo do assistente. */}
          {visited.has(t.id) && (
            <>
              {t.id === 'dashboard' && <Dashboard onNavigate={navigate} active={tab === 'dashboard'} />}
              {t.id === 'entrada' && <DataInputScreen repId={repId} onNavigate={navigate} />}
              {t.id === 'oportunidades' && (
                <OpportunitiesView
                  key={filtersKey} repId={repId} initialFilters={pendingFilters} onNavigate={navigate}
                  active={tab === 'oportunidades'}
                />
              )}
              {t.id === 'configuracoes' && <SettingsScreen />}
            </>
          )}
        </div>
      ))}
    </div>
  )
}
