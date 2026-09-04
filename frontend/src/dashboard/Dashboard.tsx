import { useEffect, useState } from 'react'
import { getDashboardMetrics, type DashboardMetrics } from '../api'
import { BarChart } from './BarChart'
import { DonutChart } from './DonutChart'
import { FunnelChart } from './FunnelChart'
import { StatTile } from './StatTile'
import { FUNNEL_STAGES } from './types'

function formatCurrency(v: number): string {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
}
function formatCount(v: number): string {
  return v.toLocaleString('pt-BR')
}

export function Dashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getDashboardMetrics()
      .then(setMetrics)
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar as métricas.'))
  }, [])

  if (error) return <p className="lt-hint" role="alert">{error}</p>
  if (!metrics) return <p className="lt-hint">Carregando…</p>

  const { kpis } = metrics

  return (
    <div className="lt-dashboard">
      <div className="lt-header">
        <h2>Dashboard Executivo</h2>
        <p>Visão consolidada — dado real da sua instalação.</p>
      </div>

      <div className="lt-stat-grid">
        <StatTile label="Oportunidades identificadas" value={formatCount(kpis.opportunitiesIdentified)} />
        <StatTile label="Clientes analisados" value={formatCount(kpis.customersAnalyzed)} />
        <StatTile label="Prospects analisados" value={formatCount(kpis.prospectsAnalyzed)} />
        <StatTile label="Potencial financeiro" value={formatCurrency(kpis.financialPotentialTotal)} />
        <StatTile label="Oportunidades de produto" value={formatCount(kpis.productOpportunities)} />
        <StatTile label="Oportunidades de serviço" value={formatCount(kpis.serviceOpportunities)} />
        <StatTile label="Fabricante principal" value={kpis.topVendor ?? '—'} />
        <StatTile label="Serviço principal" value={kpis.topService ?? '—'} />
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
      </div>

      <p className="lt-hint">
        Tendência temporal e segmentação por região/segmento ficam de fora por enquanto —
        exigem histórico de status (Fase D do roadmap) e dado real de segmento/região vindo de uma fonte configurada.
      </p>
    </div>
  )
}
