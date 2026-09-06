import { useEffect, useState } from 'react'
import {
  getIcpProfile, getIcpSuggestion, listProducts, runGeoDiscovery, updateIcpProfile,
  type GeoDiscoveryResult, type ICPSuggestion, type Product,
} from './api'

// Fluxo de 4 passos desenhado com o agente Sales Engineer (consulta registrada
// em docs/specs/fase-e-prospeccao-geografica.md, módulo 6) — nunca uma tela de
// filtros técnicos. Cada passo só avança com o dado anterior válido; erro de
// endereço interrompe aqui (não deixa chegar ao passo de confirmação com
// origem inválida).
type Step = 1 | 2 | 3 | 4

export function GeoDiscoveryWizard() {
  const [step, setStep] = useState<Step>(1)
  const [products, setProducts] = useState<Product[]>([])
  const [suggestion, setSuggestion] = useState<ICPSuggestion | null | undefined>(undefined)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [repId, setRepId] = useState('')
  const [referenceProductId, setReferenceProductId] = useState('')
  const [searchOriginAddress, setSearchOriginAddress] = useState('')
  const [radiusKm, setRadiusKm] = useState(15)
  const [placeCategory, setPlaceCategory] = useState('')
  const [companySizeHint, setCompanySizeHint] = useState('')

  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [result, setResult] = useState<GeoDiscoveryResult | null>(null)

  useEffect(() => {
    Promise.all([listProducts(), getIcpProfile()])
      .then(([productList, profile]) => {
        setProducts(productList)
        if (profile.searchOriginAddress) setSearchOriginAddress(profile.searchOriginAddress)
        if (profile.radiusKm) setRadiusKm(profile.radiusKm)
        if (profile.referenceProductId) setReferenceProductId(profile.referenceProductId)
      })
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Não consegui carregar os dados iniciais.'))
  }, [])

  const goToStep3 = () => {
    setStep(3)
    if (suggestion === undefined) {
      getIcpSuggestion()
        .then(s => {
          setSuggestion(s)
          if (s) {
            setPlaceCategory(prev => prev || s.industryHint || '')
            setCompanySizeHint(prev => prev || s.companySizeHint || '')
          }
        })
        .catch(() => setSuggestion(null))
    }
  }

  const handleRun = async () => {
    setRunning(true)
    setRunError(null)
    try {
      // Salva o ICP revisado — próxima busca já vem pré-preenchida (não é
      // aplicação automática de sugestão: o usuário acabou de confirmar
      // esses valores no passo 3, revisando-os antes de chegar aqui).
      await updateIcpProfile({
        referenceProductId: referenceProductId || null, placeCategory: placeCategory || null,
        companySizeHint: companySizeHint || null, radiusKm, searchOriginAddress,
      })
      const geoResult = await runGeoDiscovery({
        repId, referenceProductId: referenceProductId || null, searchOriginAddress, radiusKm,
        placeCategory: placeCategory || null, companySizeHint: companySizeHint || null,
      })
      setResult(geoResult)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Não conseguimos completar a busca agora.')
    } finally {
      setRunning(false)
    }
  }

  const handleRestart = () => {
    setResult(null)
    setRunError(null)
    setStep(1)
  }

  if (loadError) return <p className="lt-hint" role="alert">{loadError}</p>

  if (result) {
    return (
      <div className="lt-dashboard">
        <div className="lt-header">
          <h2>Resultado da busca</h2>
        </div>
        <div className="lt-stat-grid">
          <div className="lt-stat-tile">
            <div className="lt-stat-tile__value">{result.promoted.length}</div>
            <div className="lt-stat-tile__label">Prontos para contato</div>
            <div className="lt-stat-tile__hint">Passaram no critério e já estão na sua lista de oportunidades.</div>
          </div>
          {result.deferredCount > 0 && (
            <div className="lt-stat-tile">
              <div className="lt-stat-tile__value">{result.deferredCount}</div>
              <div className="lt-stat-tile__label">Na fila para amanhã</div>
              <div className="lt-stat-tile__hint">
                Encontramos mais oportunidades boas do que a cota diária de hoje. Elas entram automaticamente na
                lista amanhã, sem precisar buscar de novo.
              </div>
            </div>
          )}
          {result.rejectedCount > 0 && (
            <div className="lt-stat-tile">
              <div className="lt-stat-tile__value">{result.rejectedCount}</div>
              <div className="lt-stat-tile__label">Fora do critério</div>
            </div>
          )}
        </div>
        {result.promoted.length > 0 && (
          <table className="lt-table">
            <thead><tr><th>Empresa</th><th>Compatibilidade</th></tr></thead>
            <tbody>
              {result.promoted.map(p => (
                <tr key={p.opportunityId}>
                  <td>{p.companyName}</td>
                  <td>{Math.round(p.score * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="lt-detail-actions">
          <button type="button" className="lt-btn" onClick={handleRestart}>Nova busca</button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="lt-header">
        <h2>Prospecção geográfica</h2>
        <p>Passo {step} de 4</p>
      </div>

      {step === 1 && (
        <div className="lt-source-card__form">
          <label className="lt-field">
            <span>Buscar prospecção para (representante)</span>
            <input value={repId} onChange={e => setRepId(e.target.value)} placeholder="Id ou nome do representante" />
          </label>
          <label className="lt-field">
            <span>A partir de qual produto ou serviço?</span>
            <select value={referenceProductId} onChange={e => setReferenceProductId(e.target.value)}>
              <option value="">Nenhum em particular</option>
              {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={() => setStep(2)} disabled={!repId.trim()}>
              Avançar
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="lt-source-card__form">
          <label className="lt-field">
            <span>Endereço de origem da busca</span>
            <input
              value={searchOriginAddress} onChange={e => setSearchOriginAddress(e.target.value)}
              placeholder="Rua, número, cidade"
            />
          </label>
          <label className="lt-field">
            <span>Raio de busca: {radiusKm} km</span>
            <input type="range" min={1} max={50} value={radiusKm} onChange={e => setRadiusKm(Number(e.target.value))} />
          </label>
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={() => setStep(1)}>Voltar</button>
            <button type="button" className="lt-btn" onClick={goToStep3} disabled={!searchOriginAddress.trim()}>
              Avançar
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="lt-source-card__form">
          {suggestion === undefined && <p className="lt-hint">Calculando sugestão…</p>}
          {suggestion === null && (
            <p className="lt-hint">
              Ainda não temos clientes satisfeitos suficientes pra sugerir automaticamente. Escolha a categoria e o
              porte manualmente.
            </p>
          )}
          {suggestion && suggestion.confidence === 'high' && (
            <p className="lt-hint">
              Com base nos seus clientes satisfeitos, sugerimos buscar <strong>{suggestion.industryHint ?? '—'}</strong>,
              porte <strong>{suggestion.companySizeHint ?? '—'}</strong>.
            </p>
          )}
          {suggestion && suggestion.confidence === 'low' && (
            <p className="lt-hint">
              Encontramos poucos clientes de referência ainda ({suggestion.sampleSize}), então esta é uma sugestão
              inicial — vale revisar antes de confirmar.
            </p>
          )}
          <label className="lt-field">
            <span>Categoria (Google Places)</span>
            <input value={placeCategory} onChange={e => setPlaceCategory(e.target.value)} placeholder="ex.: car_dealer" />
          </label>
          <label className="lt-field">
            <span>Porte-alvo</span>
            <input value={companySizeHint} onChange={e => setCompanySizeHint(e.target.value)} placeholder="ex.: média" />
          </label>
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={() => setStep(2)}>Voltar</button>
            <button type="button" className="lt-btn" onClick={() => setStep(4)}>Avançar</button>
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="lt-source-card__form">
          <p className="lt-hint">
            Vamos buscar {placeCategory || 'empresas'} {companySizeHint ? `de porte ${companySizeHint} ` : ''}
            num raio de {radiusKm}km a partir de "{searchOriginAddress}", para {repId}.
          </p>
          {runError && (
            <p className="lt-hint" role="alert">
              Não conseguimos completar a busca agora. Isso não é um problema com os seus critérios — pode ser uma
              instabilidade temporária. {runError}
            </p>
          )}
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={() => setStep(3)} disabled={running}>Voltar</button>
            <button type="button" className="lt-btn" onClick={handleRun} disabled={running} aria-busy={running}>
              {running ? 'Buscando…' : 'Buscar agora'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
