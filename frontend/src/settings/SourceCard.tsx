import { useState } from 'react'
import { testSourceConnection, updateSettings, type SourceStatus } from '../api'
import { needsCredentialsBeforeEnabling } from './logic'

const STATUS_ICON: Record<string, string> = { connected: '🟢', failed: '🔴', unknown: '⚪' }
const STATUS_LABEL: Record<string, string> = {
  connected: 'Conectado', failed: 'Sem conexão', unknown: 'Ainda não testado',
}

export function SourceCard({ source, onChange }: { source: SourceStatus; onChange: (s: SourceStatus) => void }) {
  const [formOpen, setFormOpen] = useState(false)
  const [values, setValues] = useState<Record<string, string>>({})
  const [check, setCheck] = useState(source.last_check)
  const [busy, setBusy] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const missingRequiredValue = needsCredentialsBeforeEnabling(source)

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
    const turningOn = !source.enabled
    if (turningOn && missingRequiredValue) {
      setFormOpen(true)
      return
    }
    setBusy(true)
    setSaveError(null)
    try {
      const updated = await updateSettings(source.id, turningOn, {})
      onChange(updated)
      if (turningOn) await runTest(source.id)
      else setCheck({ status: 'unknown', message: '' })
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Falha ao salvar.')
    } finally {
      setBusy(false)
    }
  }

  const handleSaveForm = async () => {
    setBusy(true)
    setSaveError(null)
    try {
      const updated = await updateSettings(source.id, true, values)
      onChange(updated)
      setFormOpen(false)
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
            <>
              <span className="lt-conn-indicator" aria-label={STATUS_LABEL[check.status]}>
                {STATUS_ICON[check.status]} {STATUS_LABEL[check.status]}
              </span>
              <button type="button" className="lt-btn" onClick={() => runTest(source.id)} disabled={busy || !source.enabled}>
                Testar de novo
              </button>
            </>
          )}
          {source.enabled === null ? (
            <span className="lt-hint">Sempre disponível</span>
          ) : (
            <label className="lt-toggle">
              <input type="checkbox" checked={source.enabled} disabled={busy || !source.implemented} onChange={handleToggle} />
              <span>{source.enabled ? 'Ligado' : 'Desligado'}</span>
            </label>
          )}
        </div>
      </div>

      {check.status === 'failed' && source.enabled && <p className="lt-hint" role="alert">{check.message}</p>}
      {saveError && <p className="lt-hint" role="alert">{saveError}</p>}

      {formOpen && (
        <div className="lt-source-card__form">
          {source.fields.map(f => (
            <label key={f.key} className="lt-field">
              <span>{f.label}</span>
              <input
                type={f.secret ? 'password' : 'text'}
                placeholder={f.has_value ? '••••••••' : ''}
                onChange={e => setValues(v => ({ ...v, [f.key]: e.target.value }))}
              />
              <span className="lt-hint">{f.help_text}</span>
            </label>
          ))}
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={handleSaveForm} disabled={busy}>
              Salvar e conectar
            </button>
            <button type="button" className="lt-btn" onClick={() => setFormOpen(false)} disabled={busy}>
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
