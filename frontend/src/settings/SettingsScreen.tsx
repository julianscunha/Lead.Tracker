import { useEffect, useState } from 'react'
import {
  listProducts, listServices, listSettings, triggerSync, type Product, type Service, type SourceStatus,
  type SyncResult,
} from '../api'
import { AiConfigSection } from './AiConfigSection'
import { FieldMappingSection } from './FieldMappingSection'
import { PortfolioSection } from './PortfolioSection'
import { RepTargetsSection } from './RepTargetsSection'
import { RulesSection } from './RulesSection'
import { SourceCard } from './SourceCard'
import { ThresholdsSection } from './ThresholdsSection'
import { InfoHint } from '../InfoHint'

export function summarizeSync(results: SyncResult[]): string {
  if (results.length === 0) return 'Nenhuma fonte habilitada — ligue uma fonte acima antes de sincronizar.'
  const companies = results.reduce((sum, r) => sum + r.companiesSynced, 0)
  const contacts = results.reduce((sum, r) => sum + r.contactsSynced, 0)
  const errors = results.flatMap(r => r.errors)
  const base = `${companies} empresa(s) e ${contacts} contato(s) sincronizados.`
  return errors.length > 0 ? `${base} Alguns erros: ${errors.join('; ')}` : base
}

export function SettingsScreen() {
  const [sources, setSources] = useState<SourceStatus[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)

  // Catálogo (produtos/serviços) elevado pra cá — Portfólio cria e Regras
  // consome; se cada seção buscasse por conta própria, um produto criado em
  // Portfólio só apareceria em Regras depois de recarregar a página inteira.
  const [products, setProducts] = useState<Product[] | null>(null)
  const [services, setServices] = useState<Service[] | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)

  useEffect(() => {
    listSettings()
      .then(setSources)
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar as configurações.'))
    Promise.all([listProducts(), listServices()])
      .then(([p, s]) => { setProducts(p); setServices(s) })
      .catch(err => setCatalogError(err instanceof Error ? err.message : 'Não consegui carregar o portfólio.'))
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    setSyncMessage(null)
    try {
      const results = await triggerSync()
      setSyncMessage(summarizeSync(results))
    } catch (err) {
      setSyncMessage(err instanceof Error ? err.message : 'Falha ao sincronizar.')
    } finally {
      setSyncing(false)
    }
  }

  if (error) return <p className="lt-alert" role="alert">{error}</p>
  if (!sources) return <p className="lt-hint">Carregando...</p>

  return (
    <div>
      <div className="lt-header lt-header-row">
        <h2>Configurações de Fontes</h2>
        <InfoHint text="Ligue as fontes de dados que o Lead.Tracker deve usar para encontrar oportunidades." />
      </div>
      <div className="lt-toolbar">
        <button type="button" className="lt-btn" onClick={handleSync} disabled={syncing} aria-busy={syncing}>
          {syncing ? 'Sincronizando…' : 'Atualizar dados'}
        </button>
      </div>
      {syncMessage && <p className="lt-hint" role="status">{syncMessage}</p>}
      <div className="lt-source-grid">
        {sources.map(s => (
          <SourceCard
            key={s.id}
            source={s}
            onChange={updated => setSources(prev => prev!.map(p => (p.id === updated.id ? updated : p)))}
          />
        ))}
      </div>

      {sources.find(s => s.id === 'salesforce')?.enabled && <FieldMappingSection />}
      <AiConfigSection />
      <ThresholdsSection />
      <PortfolioSection
        products={products} services={services} loadError={catalogError}
        onProductCreated={p => setProducts(prev => [...(prev ?? []), p])}
        onServiceCreated={s => setServices(prev => [...(prev ?? []), s])}
        onProductDeleted={id => setProducts(prev => (prev ?? []).filter(p => p.id !== id))}
        onServiceDeleted={id => setServices(prev => (prev ?? []).filter(s => s.id !== id))}
      />
      <RulesSection products={products ?? []} services={services ?? []} />
      <RepTargetsSection />
    </div>
  )
}
