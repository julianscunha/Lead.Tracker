import { BarChart } from './BarChart'
import { DonutChart } from './DonutChart'
import { FunnelChart } from './FunnelChart'
import {
  sampleCustomerVsProspect, sampleFinancialByVendor, sampleFunnelCounts,
  sampleKpis, sampleOpportunitiesByService, sampleVendorDistribution,
} from './sampleMetrics'
import { StatTile } from './StatTile'
import { FUNNEL_STAGES } from './types'

function formatCurrency(v: number): string {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
}
function formatCount(v: number): string {
  return v.toLocaleString('pt-BR')
}

export function Dashboard() {
  const kpis = sampleKpis

  return (
    <div className="lt-dashboard">
      <div className="lt-header">
        <h2>Dashboard Executivo</h2>
        <p>Visão consolidada — dados fictícios até a persistência real existir.</p>
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
          <DonutChart data={sampleVendorDistribution} emptyMessage="Sem oportunidades com fabricante identificado." />
        </section>

        <section className="lt-chart-card">
          <h3>Potencial financeiro por fabricante</h3>
          <BarChart data={sampleFinancialByVendor} formatValue={formatCurrency} emptyMessage="Sem potencial financeiro registrado." />
        </section>

        <section className="lt-chart-card">
          <h3>Oportunidades por serviço</h3>
          <BarChart data={sampleOpportunitiesByService} formatValue={formatCount} emptyMessage="Sem oportunidades de serviço." />
        </section>

        <section className="lt-chart-card">
          <h3>Clientes × Prospects</h3>
          <BarChart data={sampleCustomerVsProspect} formatValue={formatCount} emptyMessage="Sem empresas analisadas." />
        </section>

        <section className="lt-chart-card lt-chart-card--wide">
          <h3>Funil de oportunidades</h3>
          <FunnelChart stages={FUNNEL_STAGES} counts={sampleFunnelCounts} />
        </section>
      </div>

      <p className="lt-hint">
        Tendência temporal e segmentação por região/segmento ficam de fora por enquanto —
        exigem persistência histórica e um campo de segmento/região que ainda não existem no modelo.
      </p>
    </div>
  )
}
