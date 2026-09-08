import { useEffect, useState } from 'react'
import {
  getAgingSlaConfig, getGeoPromotionConfig, updateAgingSlaConfig, updateGeoPromotionConfig,
} from '../api'
import { InfoHint } from '../InfoHint'

// Achado da auditoria de UX (não-técnico): SLA de triagem e limites de
// promoção geográfica só existiam via .env/API direta — sem forma de
// ajustar pela interface.
export function ThresholdsSection() {
  const [slaDays, setSlaDays] = useState('')
  const [minScore, setMinScore] = useState('')
  const [dailyCap, setDailyCap] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState<'sla' | 'geo' | null>(null)

  useEffect(() => {
    Promise.all([getAgingSlaConfig(), getGeoPromotionConfig()])
      .then(([sla, geo]) => {
        setSlaDays(String(sla.days))
        setMinScore(String(geo.min_score))
        setDailyCap(String(geo.daily_cap))
        setLoaded(true)
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar os limites configurados.'))
  }, [])

  const saveSla = async () => {
    setSaving('sla')
    setError(null)
    setMessage(null)
    try {
      const updated = await updateAgingSlaConfig(Number(slaDays))
      setSlaDays(String(updated.days))
      setMessage('Prazo de triagem salvo.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao salvar o prazo de triagem.')
    } finally {
      setSaving(null)
    }
  }

  const saveGeo = async () => {
    setSaving('geo')
    setError(null)
    setMessage(null)
    try {
      const updated = await updateGeoPromotionConfig(Number(minScore), Number(dailyCap))
      setMinScore(String(updated.min_score))
      setDailyCap(String(updated.daily_cap))
      setMessage('Limites de promoção geográfica salvos.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao salvar os limites de promoção geográfica.')
    } finally {
      setSaving(null)
    }
  }

  if (error && !loaded) return <p className="lt-alert" role="alert">{error}</p>
  if (!loaded) return <p className="lt-hint">Carregando…</p>

  return (
    <div className="lt-source-card">
      <div className="lt-source-card__header">
        <div className="lt-header-row">
          <p className="lt-source-card__title">Limites e prazos</p>
          <InfoHint text="Controla quando uma oportunidade conta como atrasada na triagem e quantas descobertas de geolocalização entram automaticamente por dia." />
        </div>
      </div>
      <div className="lt-source-card__form">
        <label className="lt-field">
          <span>Prazo de triagem (dias)</span>
          <input
            type="number" min={1} value={slaDays}
            onChange={e => setSlaDays(e.target.value)}
          />
          <span className="lt-hint">
            Detectada sem virar qualificada nem descartada depois desse prazo conta como
            "triagem atrasada" no dashboard.
          </span>
        </label>
        <div className="lt-detail-actions">
          <button type="button" className="lt-btn" onClick={saveSla} disabled={saving === 'sla'}>
            {saving === 'sla' ? 'Salvando…' : 'Salvar prazo de triagem'}
          </button>
        </div>

        <label className="lt-field">
          <span>Score mínimo pra promoção automática</span>
          <input
            type="number" min={0} max={1} step={0.01} value={minScore}
            onChange={e => setMinScore(e.target.value)}
          />
          <span className="lt-hint">De 0.0 a 1.0 — quanto maior, mais seletiva a promoção automática.</span>
        </label>
        <label className="lt-field">
          <span>Limite diário de promoções automáticas</span>
          <input
            type="number" min={1} value={dailyCap}
            onChange={e => setDailyCap(e.target.value)}
          />
          <span className="lt-hint">Teto de descobertas geográficas promovidas automaticamente por dia.</span>
        </label>
        <div className="lt-detail-actions">
          <button type="button" className="lt-btn" onClick={saveGeo} disabled={saving === 'geo'}>
            {saving === 'geo' ? 'Salvando…' : 'Salvar limites de promoção geográfica'}
          </button>
        </div>

        {error && <p className="lt-alert" role="alert">{error}</p>}
        {message && <p className="lt-hint" role="status">{message}</p>}
      </div>
    </div>
  )
}
