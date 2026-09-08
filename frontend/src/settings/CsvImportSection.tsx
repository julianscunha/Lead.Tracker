import { useState } from 'react'
import { importCsv, type CsvImportResult } from '../api'
import { InfoHint } from '../InfoHint'

// Achado de teste manual: sem Salesforce/Google Maps configurados não havia
// nenhuma forma de colocar empresa + portfólio real no sistema em lote
// (Manual é só um stub de arquitetura). CSV reaproveita o mesmo motor de
// regras do /sync — nunca inventa fabricante/produto/serviço que não esteja
// no catálogo já cadastrado em Portfólio.
export function CsvImportSection() {
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState<'merge' | 'replace'>('merge')
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<CsvImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleImport = async () => {
    if (!file) return
    setImporting(true)
    setError(null)
    setResult(null)
    try {
      const imported = await importCsv(file, mode)
      setResult(imported)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao importar o CSV.')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="lt-source-card">
      <div className="lt-source-card__header">
        <div className="lt-header-row">
          <p className="lt-source-card__title">Importar CSV</p>
          <InfoHint text="Cadastra empresa + portfólio (o que ela já tem do seu catálogo) em lote, sem precisar de Salesforce ou Google Maps configurados. Fabricante/produto/serviço citados no arquivo precisam já existir em Portfólio — o import nunca inventa item novo no catálogo." />
        </div>
      </div>
      <div className="lt-source-card__form">
        <label className="lt-field">
          <span>Arquivo CSV</span>
          <input
            type="file" accept=".csv,text/csv"
            onChange={e => setFile(e.target.files?.[0] ?? null)}
          />
          <span className="lt-hint">
            Colunas: company_name (obrigatória), is_customer, segment, region, rep_id, vendor, product,
            service. Uma linha por empresa + item de portfólio — repita a empresa numa linha por produto/serviço.
          </span>
        </label>
        <label className="lt-field">
          <span>Empresa já cadastrada: o que fazer com o portfólio</span>
          <select value={mode} onChange={e => setMode(e.target.value as 'merge' | 'replace')}>
            <option value="merge">Adicionar aos itens já cadastrados</option>
            <option value="replace">Substituir pelos itens deste arquivo</option>
          </select>
          <span className="lt-hint">
            Adicionar preserva o que já foi cadastrado antes; Substituir descarta o portfólio anterior
            da empresa e usa só o que está neste arquivo.
          </span>
        </label>
        <div className="lt-detail-actions">
          <button type="button" className="lt-btn" onClick={handleImport} disabled={importing || !file}>
            {importing ? 'Importando…' : 'Importar'}
          </button>
        </div>
        {error && <p className="lt-alert" role="alert">{error}</p>}
        {result && (
          <div className="lt-panel">
            <p className="lt-panel-text">
              {result.companies_imported} empresa(s) importada(s), {result.portfolios_updated} portfólio(s)
              atualizado(s), {result.opportunities_generated} oportunidade(s) gerada(s).
            </p>
            {result.errors.length > 0 && (
              <ul>
                {result.errors.map((e, i) => <li key={i} className="lt-alert">{e}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
