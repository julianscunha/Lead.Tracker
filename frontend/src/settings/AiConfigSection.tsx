import { useEffect, useState } from 'react'
import { getAiConfig, updateAiConfig, type AiConfig } from '../api'

// Achado da auditoria de UX (não-técnico): antes desta seção, ativar o
// rascunho de e-mail por IA exigia editar o .env na mão — impossível pra
// um vendedor leigo. Seção própria, nunca dentro de "Fontes de Dados": IA
// não sincroniza empresa nenhuma, não é uma fonte.
export function AiConfigSection() {
  const [config, setConfig] = useState<AiConfig | null>(null)
  const [provider, setProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getAiConfig()
      .then(c => { setConfig(c); setProvider(c.provider) })
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar a configuração de IA.'))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await updateAiConfig(provider, apiKey)
      setConfig(updated)
      setApiKey('')
      setSaveMessage('Configuração de IA salva.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao salvar a configuração de IA.')
    } finally {
      setSaving(false)
    }
  }

  if (error && !config) return <p className="lt-alert" role="alert">{error}</p>
  if (!config) return <p className="lt-hint">Carregando…</p>

  return (
    <div className="lt-source-card">
      <div className="lt-source-card__header">
        <div>
          <p className="lt-source-card__title">Inteligência Artificial</p>
          <p className="lt-hint">
            Opcional — usada só pra gerar rascunho de e-mail. O Lead.Tracker funciona
            normalmente sem isso.
          </p>
        </div>
      </div>
      <div className="lt-source-card__form">
        <label className="lt-field">
          <span>Provedor de IA</span>
          <select value={provider} onChange={e => setProvider(e.target.value)}>
            <option value="">Não configurado</option>
            {config.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <label className="lt-field">
          <span>Chave de acesso do provedor</span>
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder={config.has_key ? '••••••••' : ''}
          />
          <span className="lt-hint">
            Cole aqui a chave fornecida pelo provedor escolhido. Deixe em branco pra manter
            a chave já salva.
          </span>
        </label>
        <div className="lt-detail-actions">
          <button type="button" className="lt-btn" onClick={handleSave} disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
        {error && <p className="lt-alert" role="alert">{error}</p>}
        {saveMessage && <p className="lt-hint" role="status">{saveMessage}</p>}
      </div>
    </div>
  )
}
