import { useEffect, useState } from 'react'
import { listSettings, triggerSync, type SourceStatus, type SyncResult } from '../api'
import { SourceCard } from './SourceCard'

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

  useEffect(() => {
    listSettings()
      .then(setSources)
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar as configurações.'))
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

  if (error) return <p className="lt-hint" role="alert">{error}</p>
  if (!sources) return <p className="lt-hint">Carregando...</p>

  return (
    <div>
      <div className="lt-header">
        <h2>Configurações de Fontes</h2>
        <p>Ligue as fontes de dados que o Lead.Tracker deve usar para encontrar oportunidades.</p>
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
    </div>
  )
}
