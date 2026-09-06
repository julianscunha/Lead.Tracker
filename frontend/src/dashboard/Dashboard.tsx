import { useEffect, useState } from 'react'
import { getDashboardMetrics, type DashboardMetrics, type PeriodType } from '../api'
import { BarChart } from './BarChart'
import { DonutChart } from './DonutChart'
import { FunnelChart } from './FunnelChart'
import { StatTile } from './StatTile'
import { FUNNEL_REACH_LABELS, FUNNEL_STAGES } from './types'

function formatCurrency(v: number): string {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
}
function formatCount(v: number): string {
  return v.toLocaleString('pt-BR')
}
function formatPercent(v: number): string {
  return `${Math.round(v * 100)}%`
}

export function Dashboard() {
  const [periodType, setPeriodType] = useState<PeriodType>('monthly')
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    getDashboardMetrics(periodType)
      .then(data => { if (!cancelled) setMetrics(data) })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'Não consegui carregar as métricas.') })
    return () => { cancelled = true }
  }, [periodType])

  if (error) return <p className="lt-hint" role="alert">{error}</p>
  if (!metrics) return <p className="lt-hint">Carregando…</p>

  const { kpis } = metrics
  const reachCounts: Record<string, number> = {}
  metrics.funnelReach.forEach(r => { reachCounts[FUNNEL_REACH_LABELS[r.stage] ?? r.stage] = r.reachCount })
  const reachStages = metrics.funnelReach.map(r => FUNNEL_REACH_LABELS[r.stage] ?? r.stage)

  return (
    <div className="lt-dashboard">
      <div className="lt-header">
        <h2>Dashboard Executivo</h2>
        <p>Visão consolidada — dado real da sua instalação.</p>
      </div>

      <div className="lt-stat-grid">
        <StatTile label="Oportunidades identificadas" value={formatCount(kpis.opportunitiesIdentified)}
          hint="Total de oportunidades já detectadas pelo motor, em qualquer estágio." />
        <StatTile label="Clientes analisados" value={formatCount(kpis.customersAnalyzed)}
          hint="Empresas marcadas como cliente atual em pelo menos uma fonte." />
        <StatTile label="Prospects analisados" value={formatCount(kpis.prospectsAnalyzed)}
          hint="Empresas sem relação de cliente ainda, mas já mapeadas." />
        <StatTile label="Potencial financeiro" value={formatCurrency(kpis.financialPotentialTotal)}
          hint="Soma bruta de todas as oportunidades com valor estimado — sem ponderar por confiança." />
        <StatTile label="Oportunidades de produto" value={formatCount(kpis.productOpportunities)}
          hint="Oportunidades associadas a um produto específico do portfólio." />
        <StatTile label="Oportunidades de serviço" value={formatCount(kpis.serviceOpportunities)}
          hint="Oportunidades associadas a um serviço específico do portfólio." />
        <StatTile label="Fabricante principal" value={kpis.topVendor ?? '—'}
          hint="Fabricante com mais oportunidades identificadas." />
        <StatTile label="Serviço principal" value={kpis.topService ?? '—'}
          hint="Serviço com mais oportunidades identificadas." />
      </div>

      <div className="lt-stat-grid">
        <StatTile label="Potencial ponderado (avaliado)" value={formatCurrency(metrics.weightedPotential.weightedEvaluatedTotal)}
          hint="Só oportunidades com confiança real avaliada, multiplicada pelo potencial — nunca substitui o bruto, complementa." />
        <StatTile label="Potencial ponderado (estimado)" value={formatCurrency(metrics.weightedPotential.weightedEstimatedTotal)}
          hint="Inclui também as sem confiança avaliada, usando uma estimativa conservadora — visão mais otimista que o avaliado." />
        <StatTile label="Oportunidades zumbi" value={formatCount(metrics.zombieCount)}
          hint="Paradas há mais de 30 dias no mesmo estágio — excluídas do potencial ponderado e dos cortes por rep/segmento/fonte." />
        <StatTile label="Triagem atrasada" value={formatCount(metrics.agingCount)}
          hint={`Detectadas há mais de ${metrics.agingSlaDays} dia(s) sem virar qualificada nem descartada (SLA configurável em Configurações).`} />
      </div>

      <div className="lt-chart-grid">
        <section className="lt-chart-card">
          <h3>Distribuição por fabricante</h3>
          <DonutChart data={metrics.vendorDistribution} emptyMessage="Sem oportunidades com fabricante identificado." />
        </section>

        <section className="lt-chart-card">
          <h3>Potencial financeiro por fabricante</h3>
          <BarChart data={metrics.financialByVendor} formatValue={formatCurrency} emptyMessage="Sem potencial financeiro registrado." />
        </section>

        <section className="lt-chart-card">
          <h3>Oportunidades por serviço</h3>
          <BarChart data={metrics.opportunitiesByService} formatValue={formatCount} emptyMessage="Sem oportunidades de serviço." />
        </section>

        <section className="lt-chart-card">
          <h3>Clientes × Prospects</h3>
          <BarChart data={metrics.customerVsProspect} formatValue={formatCount} emptyMessage="Sem empresas analisadas." />
        </section>

        <section className="lt-chart-card lt-chart-card--wide">
          <h3>Funil de oportunidades</h3>
          <FunnelChart stages={FUNNEL_STAGES} counts={metrics.funnelCounts} />
        </section>

        <section className="lt-chart-card lt-chart-card--wide">
          <h3>Alcance do funil</h3>
          <p className="lt-hint">
            Quantas oportunidades já chegaram em cada etapa ou passaram dela, hoje — nunca "taxa de conversão"
            (o histórico completo de quando cada uma mudou de estágio ainda não é guardado, então não dá pra
            calcular uma taxa de coorte de verdade).
          </p>
          <FunnelChart stages={reachStages} counts={reachCounts} />
        </section>

        <section className="lt-chart-card">
          <h3>Potencial por representante</h3>
          <BarChart data={metrics.potentialByRep} formatValue={formatCurrency} emptyMessage="Sem oportunidade atribuída a representante ainda." />
        </section>

        <section className="lt-chart-card">
          <h3>Potencial por segmento</h3>
          <BarChart data={metrics.potentialBySegment} formatValue={formatCurrency} emptyMessage="Sem oportunidade com segmento atribuído ainda." />
        </section>

        <section className="lt-chart-card">
          <h3>Potencial por fonte</h3>
          <BarChart data={metrics.potentialBySource} formatValue={formatCurrency} emptyMessage="Sem oportunidade com fonte atribuída ainda." />
        </section>
      </div>

      <section className="lt-chart-card">
        <div className="lt-toolbar">
          <h3>Cobertura de meta por representante</h3>
          <label className="lt-field">
            <span>Período</span>
            <select value={periodType} onChange={e => setPeriodType(e.target.value as PeriodType)}>
              <option value="monthly">Mensal</option>
              <option value="quarterly">Trimestral</option>
            </select>
          </label>
        </div>
        <p className="lt-hint">
          Pipeline atual dividido pela meta cadastrada em Configurações pra {metrics.coveragePeriodKey}. Sem meta
          definida pro representante, nunca mostra 0% — mostra "sem meta definida".
        </p>
        {metrics.repCoverage.length === 0 ? (
          <p className="lt-empty" role="status">Nenhum representante com oportunidade atribuída ainda.</p>
        ) : (
          <table className="lt-table">
            <thead>
              <tr><th>Representante</th><th>Pipeline atual</th><th>Meta</th><th>Cobertura</th></tr>
            </thead>
            <tbody>
              {metrics.repCoverage.map(c => (
                <tr key={c.repId}>
                  <td>{c.repId}</td>
                  <td>{formatCurrency(c.actual)}</td>
                  <td>{c.target === null ? '—' : formatCurrency(c.target)}</td>
                  <td>{c.coverageRatio === null ? 'Sem meta definida' : formatPercent(c.coverageRatio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <p className="lt-hint">
        Segmentação por região ainda fica de fora — exige dado real de região vindo de uma fonte configurada
        (ex.: Google Maps). Tendência temporal (série histórica) também não está aqui: o snapshot diário guarda o
        estado de hoje, não a evolução dia a dia — ver docs/specs/fase-d-dashboard-acionavel.md.
      </p>
    </div>
  )
}
