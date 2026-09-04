import { useEffect, useState } from 'react'
import { listSettings, type SourceStatus } from '../api'
import { SourceCard } from './SourceCard'

export function SettingsScreen() {
  const [sources, setSources] = useState<SourceStatus[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSettings()
      .then(setSources)
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar as configurações.'))
  }, [])

  if (error) return <p className="lt-hint" role="alert">{error}</p>
  if (!sources) return <p className="lt-hint">Carregando...</p>

  return (
    <div>
      <div className="lt-header">
        <h2>Configurações de Fontes</h2>
        <p>Ligue as fontes de dados que o Lead.Tracker deve usar para encontrar oportunidades.</p>
      </div>
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
