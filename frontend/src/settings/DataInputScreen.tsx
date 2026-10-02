import { useEffect, useState } from 'react'
import { listSettings, triggerSync, type SourceStatus, type SyncResult } from '../api'
import { GeoDiscoveryWizard } from '../GeoDiscoveryWizard'
import { InfoHint } from '../InfoHint'
import { CsvImportSection } from './CsvImportSection'
import { SourceCard } from './SourceCard'

export function summarizeSync(results: SyncResult[]): string {
  if (results.length === 0) return 'Nenhuma fonte habilitada — ligue uma fonte acima antes de sincronizar.'
  const companies = results.reduce((sum, r) => sum + r.companiesSynced, 0)
  const contacts = results.reduce((sum, r) => sum + r.contactsSynced, 0)
  const errors = results.flatMap(r => r.errors)
  const base = `${companies} empresa(s) e ${contacts} contato(s) sincronizados.`
  return errors.length > 0 ? `${base} Alguns erros: ${errors.join('; ')}` : base
}

// Porta de entrada ÚNICA de dado: conectar fontes, importar planilha, atualizar e prospectar. O que se
// faz com o dado depois (qualificar, resolver conflito, agir) fica em Oportunidades; o que calibra o
// sistema (portfólio, regras, IA, limites) fica em Configurações.
export function DataInputScreen({ repId, onNavigate }: { repId: string; onNavigate?: (tab: 'oportunidades') => void }) {
  const [sources, setSources] = useState<SourceStatus[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)

  useEffect(() => {
    listSettings()
      .then(setSources)
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar as fontes de dados.'))
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    setSyncMessage(null)
    try {
      setSyncMessage(summarizeSync(await triggerSync()))
    } catch (err) {
      setSyncMessage(err instanceof Error ? err.message : 'Falha ao sincronizar.')
    } finally {
      setSyncing(false)
    }
  }

  if (error) return <p className="lt-alert" role="alert">{error}</p>
  if (!sources) return <p className="lt-hint">Carregando…</p>

  return (
    <div>
      <div className="lt-header lt-header-row">
        <h2>Entrada de dados</h2>
        <InfoHint text="Aqui entra tudo que alimenta o Lead.Tracker: conecte suas fontes (Salesforce, site, Google Maps), importe uma planilha, atualize os dados e faça prospecção geográfica. Depois, trabalhe as oportunidades na aba Oportunidades." />
      </div>

      <section className="lt-panel" aria-labelledby="lt-input-sync">
        <div className="lt-header lt-header-row">
          <h3 id="lt-input-sync">1. Atualizar dados das fontes</h3>
          <InfoHint text="Busca de novo as empresas e contatos das fontes ligadas e roda as regras para detectar oportunidades. Valores que mudaram na própria fonte atualizam; valores que outras fontes contestam viram conflitos para você resolver em Oportunidades." />
        </div>
        <div className="lt-toolbar">
          <button type="button" className="lt-btn" onClick={handleSync} disabled={syncing} aria-busy={syncing}>
            {syncing ? 'Sincronizando…' : 'Atualizar dados'}
          </button>
          {onNavigate && (
            <button type="button" className="lt-btn" onClick={() => onNavigate('oportunidades')}>Ver oportunidades</button>
          )}
        </div>
        {syncMessage && <p className="lt-hint" role="status">{syncMessage}</p>}
      </section>

      <section aria-labelledby="lt-input-sources">
        <div className="lt-header lt-header-row">
          <h3 id="lt-input-sources">2. Fontes de dados</h3>
          <InfoHint text="Ligue as fontes que o Lead.Tracker deve usar. A planilha CSV importa empresas e portfólio em lote, sem precisar de nenhum CRM." />
        </div>
        <div className="lt-source-grid">
          <CsvImportSection />
          {sources.map(s => (
            <SourceCard
              key={s.id}
              source={s}
              onChange={updated => setSources(prev => prev!.map(p => (p.id === updated.id ? updated : p)))}
            />
          ))}
        </div>
      </section>

      <section aria-labelledby="lt-input-geo">
        <div className="lt-header lt-header-row">
          <h3 id="lt-input-geo">3. Prospecção geográfica</h3>
          <InfoHint text="Encontra empresas parecidas com os seus melhores clientes em um raio, pelo Google Maps. Requer a chave do Google Maps ligada acima." />
        </div>
        <GeoDiscoveryWizard repId={repId} />
      </section>
    </div>
  )
}
