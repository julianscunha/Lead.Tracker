import { useState } from 'react'
import { testSourceConnection, updateSettings, type SourceStatus } from '../api'

const STATUS_ICON: Record<string, string> = { connected: '🟢', failed: '🔴', unknown: '🔴' }
const STATUS_LABEL: Record<string, string> = {
  connected: 'Conectado', failed: 'Desconectado', unknown: 'Desconectado',
}

// Achado do usuário: um único fluxo pro toggle, nunca dois caminhos
// (ligar direto vs. abrir formulário) — o toggle só decide se os campos
// ficam editáveis; ligar de verdade e testar a conexão é sempre o botão
// Salvar, mesmo com campos em branco (set_env_values nunca apaga valor já
// salvo, então salvar em branco reaproveita a credencial existente).
export function SourceCard({ source, onChange }: { source: SourceStatus; onChange: (s: SourceStatus) => void }) {
  const [enabledDraft, setEnabledDraft] = useState(source.enabled === true)
  const [values, setValues] = useState<Record<string, string>>({})
  const [check, setCheck] = useState(source.last_check)
  const [busy, setBusy] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const runTest = async (sourceId: string) => {
    setBusy(true)
    try {
      const result = await testSourceConnection(sourceId)
      setCheck(result)
    } catch (err) {
      setCheck({ status: 'failed', message: err instanceof Error ? err.message : 'Falha ao testar conexão.' })
    } finally {
      setBusy(false)
    }
  }

  const handleToggle = async () => {
    if (!source.implemented) return
    const turningOn = !enabledDraft
    setEnabledDraft(turningOn)
    if (turningOn) return
    setBusy(true)
    setSaveError(null)
    try {
      const updated = await updateSettings(source.id, false, {})
      onChange(updated)
      setCheck({ status: 'unknown', message: '' })
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar.')
    } finally {
      setBusy(false)
    }
  }

  const handleSave = async () => {
    setBusy(true)
    setSaveError(null)
    try {
      const updated = await updateSettings(source.id, true, values)
      onChange(updated)
      setValues({})
      await runTest(source.id)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="lt-source-card">
      <div className="lt-source-card__header">
        <div>
          <p className="lt-source-card__title">{source.label}</p>
          {!source.implemented && <p className="lt-hint">Em breve</p>}
        </div>
        <div className="lt-source-card__status">
          {source.enabled !== null && source.implemented && (
            <span className="lt-conn-indicator" aria-label={STATUS_LABEL[check.status]}>
              {STATUS_ICON[check.status]} {STATUS_LABEL[check.status]}
            </span>
          )}
          {source.enabled === null ? (
            <span className="lt-hint">Sempre disponível</span>
          ) : (
            <label className="lt-toggle">
              <input
                type="checkbox"
                className="lt-toggle__input"
                checked={enabledDraft}
                disabled={busy || !source.implemented}
                onChange={handleToggle}
                aria-label={`Fonte ${source.label}`}
              />
              <span className="lt-toggle__track"><span className="lt-toggle__knob" /></span>
              <span>{enabledDraft ? 'Ligado' : 'Desligado'}</span>
            </label>
          )}
        </div>
      </div>

      {check.status === 'failed' && source.enabled && <p className="lt-alert" role="alert">{check.message}</p>}
      {saveError && <p className="lt-alert" role="alert">{saveError}</p>}

      {source.enabled !== null && (
        <div className="lt-source-card__form">
          {source.fields.map(f => (
            <label key={f.key} className="lt-field">
              <span>{f.label}</span>
              <input
                type={f.secret ? 'password' : 'text'}
                placeholder={f.has_value ? '••••••••' : ''}
                disabled={!enabledDraft}
                onChange={e => setValues(v => ({ ...v, [f.key]: e.target.value }))}
              />
              <span className="lt-hint">{f.help_text}</span>
            </label>
          ))}
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={handleSave} disabled={busy || !enabledDraft}>
              Salvar e conectar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
