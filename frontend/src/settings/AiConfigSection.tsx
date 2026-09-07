import { useEffect, useState } from 'react'
import { getAiConfig, updateAiConfig, type AiConfig, type AiModelOption } from '../api'

const DEFAULT_MODEL_SENTINEL = '__custom__'

// Espelha core/routes_settings.py::_MODEL_TIERS só pra pré-visualizar as
// opções de um provedor ainda não salvo (o dropdown de provedor muda antes
// do usuário clicar em Salvar) — a validação e a lista definitiva continuam
// vindo do backend a cada resposta de getAiConfig/updateAiConfig.
const MODEL_TIERS_PREVIEW: Record<string, AiModelOption[]> = {
  openai: [
    { value: 'gpt-5-mini', label: 'Barato (gpt-5-mini)' },
    { value: 'gpt-5', label: 'Equilibrado (gpt-5)' },
    { value: 'gpt-5-pro', label: 'Caro (gpt-5-pro)' },
  ],
  gemini: [
    { value: 'gemini-2.5-flash-lite', label: 'Barato (gemini-2.5-flash-lite)' },
    { value: 'gemini-2.5-flash', label: 'Equilibrado (gemini-2.5-flash)' },
    { value: 'gemini-2.5-pro', label: 'Caro (gemini-2.5-pro)' },
  ],
  claude: [
    { value: 'claude-haiku-4-5', label: 'Barato (claude-haiku-4-5)' },
    { value: 'claude-sonnet-5', label: 'Equilibrado (claude-sonnet-5)' },
    { value: 'claude-opus-5', label: 'Caro (claude-opus-5)' },
  ],
}

// Achado da auditoria de UX (não-técnico): antes desta seção, ativar o
// rascunho de e-mail por IA exigia editar o .env na mão — impossível pra
// um vendedor leigo. Seção própria, nunca dentro de "Fontes de Dados": IA
// não sincroniza empresa nenhuma, não é uma fonte.
export function AiConfigSection() {
  const [config, setConfig] = useState<AiConfig | null>(null)
  const [provider, setProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getAiConfig()
      .then(c => { setConfig(c); setProvider(c.provider); setModel(c.model) })
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar a configuração de IA.'))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await updateAiConfig(provider, apiKey, model)
      setConfig(updated)
      setModel(updated.model)
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

  const modelOptions = provider === config.provider ? config.model_options : (MODEL_TIERS_PREVIEW[provider] ?? [])
  const isFreeformModel = modelOptions.length === 0
  const showsCustomInput = isFreeformModel || (model !== '' && !modelOptions.some(o => o.value === model))

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
          <select
            value={provider}
            onChange={e => { setProvider(e.target.value); setModel('') }}
          >
            <option value="">Não configurado</option>
            {config.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        {provider && (
          isFreeformModel ? (
            <label className="lt-field">
              <span>Modelo</span>
              <input
                value={model}
                onChange={e => setModel(e.target.value)}
                placeholder="ex.: openai/gpt-4o-mini"
              />
              <span className="lt-hint">
                OpenRouter dá acesso a qualquer modelo pelo nome exato — deixe em branco
                pra usar o padrão do OpenRouter.
              </span>
            </label>
          ) : (
            <label className="lt-field">
              <span>Modelo</span>
              <select
                value={showsCustomInput ? DEFAULT_MODEL_SENTINEL : model}
                onChange={e => setModel(e.target.value === DEFAULT_MODEL_SENTINEL ? '' : e.target.value)}
              >
                <option value={DEFAULT_MODEL_SENTINEL}>Padrão do provedor</option>
                {modelOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
          )
        )}
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
