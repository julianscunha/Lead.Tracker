import { FUNNEL_STAGES } from './types'

// Fictício, só pra exercitar a UI — espelha a forma de core/dashboard_metrics.py.
// Dashboard ainda não busca dado real via API (endpoint de métricas fica pra depois).
export const sampleKpis = {
  opportunitiesIdentified: 3,
  customersAnalyzed: 2,
  prospectsAnalyzed: 1,
  financialPotentialTotal: 48000,
  productOpportunities: 1,
  serviceOpportunities: 2,
  topVendor: 'Veeam',
  topService: 'FinOps',
}

export const sampleVendorDistribution = [
  { label: 'Veeam', value: 5 },
  { label: 'VMware', value: 3 },
  { label: 'AWS', value: 2 },
]

export const sampleFinancialByVendor = [
  { label: 'Veeam', value: 48000 },
  { label: 'VMware', value: 22000 },
  { label: 'AWS', value: 9000 },
]

export const sampleOpportunitiesByService = [
  { label: 'FinOps', value: 4 },
  { label: 'Assessment de DR', value: 2 },
]

export const sampleCustomerVsProspect = [
  { label: 'Clientes', value: 2 },
  { label: 'Prospects', value: 1 },
]

export const sampleFunnelCounts: Record<string, number> = {
  [FUNNEL_STAGES[0]]: 6,
  [FUNNEL_STAGES[1]]: 4,
  [FUNNEL_STAGES[2]]: 2,
  [FUNNEL_STAGES[3]]: 1,
}
