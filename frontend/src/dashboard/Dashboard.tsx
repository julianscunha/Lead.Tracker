import { useEffect, useRef, useState } from 'react'
import { getDashboardMetrics, type DashboardMetrics, type PeriodType } from '../api'
import { BarChart } from './BarChart'
import { DashSection } from './DashSection'
import { DonutChart } from './DonutChart'
import { formatCount, formatCurrency, formatPercent } from './format'
import { FunnelChart } from './FunnelChart'
import { RepCategoryMatrix } from './RepCategoryMatrix'
import { StatTile } from './StatTile'
import type { FilterState } from '../Filters'
import { InfoHint } from '../InfoHint'
import { FUNNEL_REACH_LABELS, FUNNEL_STAGES } from './types'

export function Dashboard({ onNavigate, active = true }: {
  onNavigate?: (tab: 'oportunidades', filters?: Partial<FilterState>) => void
  /** A aba fica montada ao trocar; ao voltar para ela os números são recarregados. */
  active?: boolean
} = {}) {
  const [periodType, setPeriodType] = useState<PeriodType>('monthly')
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)
  const wasActive = useRef(active)
  useEffect(() => {
    if (active && !wasActive.current) setReloadKey(k => k + 1)
    wasActive.current = active
  }, [active])

  useEffect(() => {
    let cancelled = false
    setError(null)
    setLoading(true)
    getDashboardMetrics(periodType)
      .then(data => { if (!cancelled) setMetrics(data) })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'Não consegui carregar as métricas.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [periodType, reloadKey])

  if (error && !metrics) {
    return (
      <div role="alert">
        <p className="lt-alert">{error}</p>
        <button type="button" className="lt-btn" onClick={() => setReloadKey(k => k + 1)}>Tentar de novo</button>
      </div>
    )
  }
  if (!metrics) return <p className="lt-empty" role="status">Carregando…</p>

  const { kpis } = metrics
  const reachCounts: Record<string, number> = {}
  metrics.funnelReach.forEach(r => { reachCounts[FUNNEL_REACH_LABELS[r.stage] ?? r.stage] = r.reachCount })
  const reachStages = metrics.funnelReach.map(r => FUNNEL_REACH_LABELS[r.stage] ?? r.stage)

  return (
    <section className="lt-dashboard" aria-labelledby="lt-dash-title" aria-busy={loading}>
      <div className="lt-header lt-header-row">
        <h2 id="lt-dash-title">Dashboard Executivo</h2>
        <InfoHint text="Visão consolidada — dado real da sua instalação." />
      </div>

      <DashSection id="lt-dash-today" title="Hoje: o que fazer?" description="O que pede uma decisão agora.">
        <div className="lt-stat-grid">
          <StatTile label="Triagem atrasada" value={formatCount(metrics.agingCount)}
            tone={metrics.agingCount > 0 ? 'attention' : undefined}
            onClick={onNavigate ? () => onNavigate('oportunidades', { status: 'detected', onlyAging: true }) : undefined}
            linkLabel="Ver as detectadas →"
            action={`Vale qualificar ou descartar as detectadas há mais de ${metrics.agingSlaDays} dia(s).`}
            hint={`Detectadas há mais de ${metrics.agingSlaDays} dia(s) sem virar qualificada nem descartada (SLA configurável em Configurações).`} />
          <StatTile label="Oportunidades zumbi" value={formatCount(metrics.zombieCount)}
            tone={metrics.zombieCount > 0 ? 'attention' : undefined}
            action="Vale decidir: retomar o contato ou descartar."
            hint="Paradas há mais de 30 dias no mesmo estágio — excluídas do potencial ponderado e dos cortes por rep/segmento/fonte." />
          <StatTile label="Oportunidades identificadas" value={formatCount(kpis.opportunitiesIdentified)}
            onClick={onNavigate ? () => onNavigate('oportunidades', {}) : undefined}
            hint="Total de oportunidades já detectadas pelo motor, em qualquer estágio." />
        </div>
      </DashSection>

      <DashSection id="lt-dash-pipeline" title="Pipeline: como está?" description="Volume, valor e andamento das oportunidades.">
        <div className="lt-stat-grid">
          <StatTile label="Potencial financeiro" value={formatCurrency(kpis.financialPotentialTotal)}
            hint="Soma bruta de todas as oportunidades com valor estimado — sem ponderar por confiança." />
          <StatTile label="Potencial ponderado (avaliado)" value={formatCurrency(metrics.weightedPotential.weightedEvaluatedTotal)}
            hint="Só oportunidades com confiança real avaliada, multiplicada pelo potencial — nunca substitui o bruto, complementa." />
          <StatTile label="Potencial ponderado (estimado)" value={formatCurrency(metrics.weightedPotential.weightedEstimatedTotal)}
            hint="Inclui também as sem confiança avaliada, usando uma estimativa conservadora — visão mais otimista que o avaliado." />
        </div>

        <div className="lt-chart-grid">
          <div role="group" className="lt-chart-card lt-chart-card--wide" aria-labelledby="lt-chart-funnel">
            <h4 id="lt-chart-funnel">Funil de oportunidades</h4>
            <FunnelChart stages={FUNNEL_STAGES} counts={metrics.funnelCounts} />
          </div>

          <div role="group" className="lt-chart-card lt-chart-card--wide" aria-labelledby="lt-chart-reach">
            <div className="lt-header-row">
              <h4 id="lt-chart-reach">Alcance do funil</h4>
              <InfoHint text={'Quantas oportunidades já chegaram em cada etapa ou passaram dela, hoje — nunca "taxa de conversão" (o histórico completo de quando cada uma mudou de estágio ainda não é guardado, então não dá pra calcular uma taxa de coorte de verdade).'} />
            </div>
            <FunnelChart stages={reachStages} counts={reachCounts} />
          </div>
        </div>

        <details className="lt-dash-more">
          <summary>Mais indicadores do pipeline (clientes, prospects, produto, serviço, por fabricante, segmento e fonte)</summary>
          <div className="lt-stat-grid">
            <StatTile label="Clientes analisados" value={formatCount(kpis.customersAnalyzed)}
              hint="Empresas marcadas como cliente atual em pelo menos uma fonte." />
            <StatTile label="Prospects analisados" value={formatCount(kpis.prospectsAnalyzed)}
              hint="Empresas sem relação de cliente ainda, mas já mapeadas." />
            <StatTile label="Oportunidades de produto" value={formatCount(kpis.productOpportunities)}
              hint="Oportunidades associadas a um produto específico do portfólio." />
            <StatTile label="Oportunidades de serviço" value={formatCount(kpis.serviceOpportunities)}
              hint="Oportunidades associadas a um serviço específico do portfólio." />
          </div>
          <div className="lt-chart-grid">
          <div role="group" className="lt-chart-card" aria-labelledby="lt-chart-vendor-money">
            <h4 id="lt-chart-vendor-money">Potencial financeiro por fabricante</h4>
            <BarChart data={metrics.financialByVendor} formatValue={formatCurrency} emptyMessage="Sem potencial financeiro registrado." />
          </div>

          <div role="group" className="lt-chart-card" aria-labelledby="lt-chart-service">
            <h4 id="lt-chart-service">Oportunidades por serviço</h4>
            <BarChart data={metrics.opportunitiesByService} formatValue={formatCount} emptyMessage="Sem oportunidades de serviço." />
          </div>

          <div role="group" className="lt-chart-card" aria-labelledby="lt-chart-segment">
            <h4 id="lt-chart-segment">Potencial por segmento</h4>
            <BarChart data={metrics.potentialBySegment} formatValue={formatCurrency} emptyMessage="Sem oportunidade com segmento atribuído ainda." />
          </div>

          <div role="group" className="lt-chart-card" aria-labelledby="lt-chart-source">
            <h4 id="lt-chart-source">Potencial por fonte</h4>
            <BarChart data={metrics.potentialBySource} formatValue={formatCurrency} emptyMessage="Sem oportunidade com fonte atribuída ainda." />
          </div>

          <div role="group" className="lt-chart-card" aria-labelledby="lt-chart-customer">
            <h4 id="lt-chart-customer">Clientes × Prospects</h4>
            <BarChart data={metrics.customerVsProspect} formatValue={formatCount} emptyMessage="Sem empresas analisadas." />
          </div>
          </div>
        </details>
      </DashSection>

      <DashSection
        id="lt-dash-reps" title="Representantes: como está cada um?"
        description="Cobertura de meta no período escolhido e onde as oportunidades de cada rep estão hoje."
        actions={(
          <label className="lt-field lt-dash-section__period">
            <span>Período</span>
            <select value={periodType} onChange={e => setPeriodType(e.target.value as PeriodType)}>
              <option value="monthly">Mensal</option>
              <option value="quarterly">Trimestral</option>
            </select>
          </label>
        )}
      >
        {error && (
          <div>
            <p className="lt-alert" role="alert">{error} Os dados abaixo ainda são de {metrics.coveragePeriodKey}.</p>
            <button type="button" className="lt-btn" onClick={() => setReloadKey(k => k + 1)}>Tentar de novo</button>
          </div>
        )}
        {loading && <p className="lt-hint" role="status">Atualizando…</p>}

        <div className="lt-chart-grid">
          <div role="group" className="lt-chart-card lt-chart-card--wide" aria-labelledby="lt-chart-coverage">
            <div className="lt-header-row">
              <h4 id="lt-chart-coverage">Cobertura de meta ({metrics.coveragePeriodKey})</h4>
              <InfoHint text={`Pipeline atual dividido pela meta cadastrada em Configurações pra ${metrics.coveragePeriodKey}. Sem meta definida pro representante, nunca mostra 0% — mostra "sem meta definida".`} />
            </div>
            {metrics.repCoverage.length === 0 ? (
              <p className="lt-empty" role="status">Nenhum representante com oportunidade atribuída ainda.</p>
            ) : (
              <table className="lt-table">
                <thead>
                  <tr><th scope="col">Representante</th><th scope="col">Pipeline atual</th><th scope="col">Meta</th><th scope="col">Cobertura</th></tr>
                </thead>
                <tbody>
                  {metrics.repCoverage.map(c => (
                    <tr key={c.repId}>
                      <th scope="row">{c.repId}</th>
                      <td>{formatCurrency(c.actual)}</td>
                      <td>{c.target === null ? '—' : formatCurrency(c.target)}</td>
                      <td>{c.coverageRatio === null ? 'Sem meta definida' : formatPercent(c.coverageRatio)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div role="group" className="lt-chart-card" aria-labelledby="lt-chart-rep-money">
            <h4 id="lt-chart-rep-money">Potencial por representante</h4>
            <BarChart data={metrics.potentialByRep} formatValue={formatCurrency} emptyMessage="Sem oportunidade atribuída a representante ainda." />
          </div>

          <div role="group" className="lt-chart-card lt-chart-card--wide" aria-labelledby="lt-chart-matrix">
            <div className="lt-header-row">
              <h4 id="lt-chart-matrix">Onde as oportunidades estão hoje, por rep e categoria</h4>
              <InfoHint text="Quantas oportunidades de cada representante, em cada categoria do portfólio, já chegaram a cada estágio. É uma foto de hoje, sem histórico de transição." />
            </div>
            <RepCategoryMatrix />
          </div>
        </div>
      </DashSection>

      <details className="lt-dash-more">
        <summary>Mais detalhes e limitações</summary>
        <div className="lt-chart-grid">
          <div role="group" className="lt-chart-card" aria-labelledby="lt-chart-vendor-donut">
            <h4 id="lt-chart-vendor-donut">Distribuição por fabricante</h4>
            <DonutChart data={metrics.vendorDistribution} emptyMessage="Sem oportunidades com fabricante identificado." />
          </div>
        </div>
        <p className="lt-hint">
          Fabricante principal: {kpis.topVendor ?? '—'}. Serviço principal: {kpis.topService ?? '—'}.
        </p>
        <p className="lt-hint">
          Segmentação por região ainda fica de fora: exige dado de região vindo de uma fonte configurada
          (ex.: Google Maps). Tendência ao longo do tempo também não aparece: a tela mostra o estado de hoje,
          porque a evolução dia a dia ainda não é guardada.
        </p>
      </details>
    </section>
  )
}
