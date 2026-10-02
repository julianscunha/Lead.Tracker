import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getRepCategoryReach, listOpportunities, type RepCategoryReach } from '../api'
import { InfoHint } from '../InfoHint'
import type { OpportunityRow } from '../types'
import { formatPercent } from './format'
import { allCategories, allReps, buildMatrix, cellColors, DEFAULT_STAGE, REACH_STAGES } from './repCategory'
import { FUNNEL_REACH_LABELS } from './types'
import { useIsDarkTheme } from './useIsDarkTheme'

const WARNING = 'Retrato do momento, não taxa de conversão: mostra quantas oportunidades já chegaram a cada estágio, sem histórico de transição. Use para decidir o que perguntar ao rep, não para avaliá-lo.'

interface Selected { rep: string; category: string; ids: string[]; detail: string }

function toggle(set: Set<string>, value: string): Set<string> {
  const next = new Set(set)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  return next
}

export function RepCategoryMatrix() {
  const dark = useIsDarkTheme()
  const [data, setData] = useState<RepCategoryReach | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stage, setStage] = useState(DEFAULT_STAGE)
  const [hiddenReps, setHiddenReps] = useState<Set<string>>(new Set())
  const [hiddenCategories, setHiddenCategories] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Selected | null>(null)
  const [deals, setDeals] = useState<OpportunityRow[] | null>(null)
  const [dealsError, setDealsError] = useState<string | null>(null)
  const dealsRequest = useRef<Promise<OpportunityRow[]> | null>(null)
  const panelTitle = useRef<HTMLHeadingElement>(null)
  const trigger = useRef<HTMLElement | null>(null)

  const load = useCallback(() => {
    setError(null)
    getRepCategoryReach()
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar o alcance por representante e categoria.'))
  }, [])
  useEffect(load, [load])

  // Painel abre sem o foco se mexer sozinho: leva o foco pro título (leitor de tela anuncia o conteúdo novo).
  useEffect(() => { if (selected) panelTitle.current?.focus() }, [selected])

  const view = useMemo(() => (data ? buildMatrix(data, stage, hiddenReps, hiddenCategories) : null), [data, stage, hiddenReps, hiddenCategories])

  // Uma única requisição em andamento/cacheada; erro libera nova tentativa.
  const loadDeals = useCallback(() => {
    setDealsError(null)
    if (!dealsRequest.current) dealsRequest.current = listOpportunities()
    dealsRequest.current.then(setDeals).catch(err => {
      dealsRequest.current = null
      setDealsError(err instanceof Error ? err.message : 'Não consegui carregar as oportunidades.')
    })
  }, [])

  const openDeals = (s: Selected, el: HTMLElement) => {
    trigger.current = el
    setSelected(s)
    if (!deals) loadDeals()
  }
  const closeDeals = () => {
    setSelected(null)
    trigger.current?.focus()
  }

  if (error) {
    return (
      <div>
        <p className="lt-alert" role="alert">{error}</p>
        <button type="button" className="lt-btn" onClick={load}>Tentar de novo</button>
      </div>
    )
  }
  if (!data || !view) return <p className="lt-empty" role="status">Carregando…</p>
  if (data.cells.length === 0) {
    return <p className="lt-empty" role="status">Nenhuma oportunidade com representante atribuído ainda.</p>
  }

  const stageLabel = FUNNEL_REACH_LABELS[stage] ?? stage
  // Filtro que esconde o par aberto fecha o painel (nunca fica órfão).
  const panel = selected && !hiddenReps.has(selected.rep) && !hiddenCategories.has(selected.category) ? selected : null
  const panelIds = panel ? new Set(panel.ids) : null
  const panelDeals = panelIds && deals ? deals.filter(d => panelIds.has(d.id)) : []

  return (
    <div className="lt-matrix">
      <p className="lt-hint lt-matrix__warning">{WARNING}</p>
      <div className="lt-toolbar lt-matrix__toolbar">
        <label className="lt-field">
          <span>Chegou a</span>
          <select value={stage} onChange={e => setStage(e.target.value)}>
            {REACH_STAGES.map(s => <option key={s} value={s}>{FUNNEL_REACH_LABELS[s] ?? s} ou além</option>)}
          </select>
        </label>
        <FilterList label="Representantes" options={allReps(data)} hidden={hiddenReps} onToggle={v => setHiddenReps(h => toggle(h, v))} />
        <FilterList label="Categorias" options={allCategories(data)} hidden={hiddenCategories} onToggle={v => setHiddenCategories(h => toggle(h, v))} />
      </div>

      <p className="lt-hint" role="status">{view.summary}. Mínimo de {data.minSample} oportunidades por par (configurável em Configurações).</p>

      <div className="lt-matrix__scroll" role="region" aria-label="Alcance do funil por representante e categoria" tabIndex={0}>
        <table className="lt-table lt-matrix__table">
          <caption className="lt-matrix__caption">
            Onde as oportunidades estão hoje, por rep e categoria — percentual que já chegou a {stageLabel} ou além
          </caption>
          <thead>
            <tr>
              <th scope="col">Representante</th>
              {view.categories.map(c => <th key={c} scope="col">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {view.reps.map((rep, i) => (
              <tr key={rep}>
                <th scope="row">{rep}</th>
                {view.rows[i].map((v, j) => {
                  const cat = view.categories[j]
                  if (v.kind === 'none') {
                    return <td key={cat} className="lt-matrix__cell lt-matrix__cell--none">—<span className="lt-sr-only"> sem oportunidades neste par</span></td>
                  }
                  const colors = v.intensity === null ? undefined : cellColors(v.intensity, dark)
                  return (
                    <td key={cat} className="lt-matrix__cell">
                      <button
                        type="button"
                        className={`lt-matrix__btn${v.kind === 'insufficient' ? ' lt-matrix__btn--insufficient' : ''}${v.kind === 'value' && v.intensity === 0 ? ' lt-matrix__btn--zero' : ''}`}
                        style={colors ? { background: colors.background, color: colors.color } : undefined}
                        title={v.tooltip} aria-label={v.ariaLabel}
                        onClick={e => openDeals({ rep, category: cat, ids: v.opportunityIds, detail: v.tooltip }, e.currentTarget)}
                      >
                        {v.text}{v.fragile && <span aria-hidden="true" className="lt-matrix__mark">*</span>}
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Mediana do time</th>
              {view.reference.map((r, j) => (
                <td key={view.categories[j]} className="lt-matrix__ref">
                  {r === null ? 'sem referência' : formatPercent(r)}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      <ul className="lt-matrix__legend" aria-label="Legenda">
        <li><span className="lt-matrix__swatch lt-matrix__swatch--ramp" aria-hidden="true" />0% a 100% (escala fixa)</li>
        <li><span className="lt-matrix__swatch lt-matrix__swatch--zero" aria-hidden="true" />0% real, com amostra suficiente</li>
        <li><span className="lt-matrix__swatch lt-matrix__swatch--insufficient" aria-hidden="true" />Dado insuficiente (n abaixo de {data.minSample})</li>
        <li><span className="lt-matrix__mark" aria-hidden="true">*</span>Amostra pequena (menos de {data.minSample * 2}): oscila muito</li>
      </ul>
      <p className="lt-hint">
        Alcance acumulado: oportunidade que chegou ao estágio escolhido ou além. Sem ranking — compare dentro do contexto da categoria.
        {data.unassignedCount > 0 && ` ${data.unassignedCount} oportunidade(s) sem representante atribuído ficam fora da matriz.`}
      </p>

      {panel && (
        <div className="lt-matrix__deals">
          <div className="lt-header-row">
            <h5 ref={panelTitle} tabIndex={-1}>Oportunidades de {panel.rep} em {panel.category}</h5>
            <InfoHint text="Os deals por trás da célula: vale olhá-los um a um antes de tirar qualquer conclusão." />
            <button type="button" className="lt-btn" onClick={closeDeals}>Fechar</button>
          </div>
          {panel.detail.split('\n').map(line => <p key={line} className="lt-hint">{line}</p>)}
          {dealsError ? (
            <div>
              <p className="lt-alert" role="alert">{dealsError}</p>
              <button type="button" className="lt-btn" onClick={loadDeals}>Tentar de novo</button>
            </div>
          ) : !deals ? <p className="lt-hint" role="status">Carregando…</p>
            : (
              <table className="lt-table" aria-label={`Oportunidades de ${panel.rep} em ${panel.category}`}>
                <thead><tr><th scope="col">Empresa</th><th scope="col">Estágio</th></tr></thead>
                <tbody>
                  {panelDeals.map(d => <tr key={d.id}><td>{d.companyName}</td><td>{FUNNEL_REACH_LABELS[d.status] ?? d.status}</td></tr>)}
                  {panelDeals.length === 0 && <tr><td colSpan={2}>Nenhuma oportunidade viva neste par agora.</td></tr>}
                </tbody>
              </table>
            )}
        </div>
      )}
    </div>
  )
}

function FilterList({ label, options, hidden, onToggle }: {
  label: string; options: string[]; hidden: Set<string>; onToggle: (v: string) => void
}) {
  return (
    <details className="lt-matrix__filter">
      <summary>{label}{hidden.size > 0 ? ` (${options.length - hidden.size} de ${options.length})` : ''}</summary>
      <ul>
        {options.map(o => (
          <li key={o}>
            <label><input type="checkbox" checked={!hidden.has(o)} onChange={() => onToggle(o)} /><span>{o}</span></label>
          </li>
        ))}
      </ul>
    </details>
  )
}
