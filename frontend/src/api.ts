import type { OpportunityRow } from './types'

const BASE = '/api/v1/modules/lead_tracker'

function toExportRow(row: OpportunityRow) {
  return {
    company_name: row.companyName,
    is_customer: row.isCustomer,
    opportunity_score: row.opportunityScore,
    financial_potential: row.financialPotential,
    product: row.product,
    service: row.service,
    priority: row.priority,
    sources: row.sources.map(s => s.type),
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function friendlyError(resp: Response): Promise<string> {
  try {
    const data = await resp.json()
    return data.detail ?? 'Falha ao processar a solicitação.'
  } catch {
    return 'Falha ao processar a solicitação.'
  }
}

export async function exportOpportunitiesPdf(rows: OpportunityRow[], filtersSummary: string): Promise<void> {
  const resp = await fetch(`${BASE}/exports/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: rows.map(toExportRow), filters_summary: filtersSummary }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  downloadBlob(await resp.blob(), 'oportunidades.pdf')
}

export async function exportOpportunitiesExcel(rows: OpportunityRow[]): Promise<void> {
  const resp = await fetch(`${BASE}/exports/excel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: rows.map(toExportRow) }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  downloadBlob(await resp.blob(), 'oportunidades.xlsx')
}

export interface EmailDraft {
  subject: string
  greeting: string
  body: string
  cta: string
}

export async function generateEmailDraft(row: OpportunityRow): Promise<EmailDraft> {
  const resp = await fetch(`${BASE}/email-draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company_name: row.companyName,
      opportunity_type: row.type,
      evidence: row.evidence,
      justification: row.justification,
      portfolio: { produtos_atuais: row.currentProducts, produtos_recomendados: row.recommendedProducts },
    }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

export interface SourceField {
  key: string
  label: string
  help_text: string
  secret: boolean
  has_value: boolean
}

export interface LastCheck {
  status: 'connected' | 'failed' | 'unknown'
  message: string
}

export interface SourceStatus {
  id: string
  label: string
  implemented: boolean
  enabled: boolean | null
  fields: SourceField[]
  last_check: LastCheck
}

export async function listSettings(): Promise<SourceStatus[]> {
  const resp = await fetch(`${BASE}/settings`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

export async function updateSettings(sourceId: string, enabled: boolean | null, fields: Record<string, string>): Promise<SourceStatus> {
  const resp = await fetch(`${BASE}/settings/${sourceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled, fields }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

export async function testSourceConnection(sourceId: string): Promise<LastCheck> {
  const resp = await fetch(`${BASE}/settings/${sourceId}/test`, { method: 'POST' })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

// ── Dado real (Fase B.1) ─────────────────────────────────────────────────────
// Backend fala snake_case (convenção Python já usada nas outras rotas);
// as funções abaixo adaptam pra camelCase (convenção do frontend).

interface OpportunityApiRow {
  id: string
  company_id: string
  company_name: string
  is_customer: boolean
  type: string
  product_id: string | null
  product_name: string | null
  service_id: string | null
  service_name: string | null
  opportunity_score: number | null
  financial_potential: number | null
  strategic_score: number | null
  confidence_score: number | null
  evidence: string[]
  justification: string | null
  sources: { type: string; confidence: number }[]
  status: OpportunityRow['status']
}

/** priority não existe no domínio (core/models.py) — derivado do score real,
 * nunca inventado. Mesmos limiares usados pra ordenar por prioridade em OpportunityTable. */
export function derivePriority(score: number | null): OpportunityRow['priority'] {
  if (score === null) return 'baixa'
  if (score >= 0.7) return 'alta'
  if (score >= 0.4) return 'média'
  return 'baixa'
}

function fromApiRow(r: OpportunityApiRow): OpportunityRow {
  return {
    id: r.id,
    companyName: r.company_name,
    isCustomer: r.is_customer,
    opportunityScore: r.opportunity_score,
    financialPotential: r.financial_potential,
    type: r.type,
    product: r.product_name,
    service: r.service_name,
    priority: derivePriority(r.opportunity_score),
    sources: r.sources,
    status: r.status,
    evidence: r.evidence,
    justification: r.justification,
    confidenceScore: r.confidence_score,
    // Sem fonte real ainda de "o que a empresa já tem" (Fase B.1 não popula
    // portfólio por empresa — ver docs/specs/fase-b1-ligacao-real.md).
    currentProducts: [],
    recommendedProducts: r.product_name ? [r.product_name] : [],
    recommendedServices: r.service_name ? [r.service_name] : [],
  }
}

export async function listOpportunities(): Promise<OpportunityRow[]> {
  const resp = await fetch(`${BASE}/opportunities`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const data: OpportunityApiRow[] = await resp.json()
  return data.map(fromApiRow)
}

export interface SyncResult {
  sourceId: string
  companiesSynced: number
  contactsSynced: number
  errors: string[]
}

export async function triggerSync(): Promise<SyncResult[]> {
  const resp = await fetch(`${BASE}/sync`, { method: 'POST' })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const data = await resp.json()
  return data.map((r: { source_id: string; companies_synced: number; contacts_synced: number; errors: string[] }) => ({
    sourceId: r.source_id, companiesSynced: r.companies_synced, contactsSynced: r.contacts_synced, errors: r.errors,
  }))
}

export interface DashboardMetrics {
  kpis: {
    opportunitiesIdentified: number
    customersAnalyzed: number
    prospectsAnalyzed: number
    financialPotentialTotal: number
    productOpportunities: number
    serviceOpportunities: number
    topVendor: string | null
    topService: string | null
  }
  vendorDistribution: { label: string; value: number }[]
  financialByVendor: { label: string; value: number }[]
  opportunitiesByService: { label: string; value: number }[]
  customerVsProspect: { label: string; value: number }[]
  funnelCounts: Record<string, number>
}

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  const resp = await fetch(`${BASE}/dashboard-metrics`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const d = await resp.json()
  const pairs = (arr: [string, number][]) => arr.map(([label, value]) => ({ label, value }))
  return {
    kpis: {
      opportunitiesIdentified: d.kpis.opportunities_identified,
      customersAnalyzed: d.kpis.customers_analyzed,
      prospectsAnalyzed: d.kpis.prospects_analyzed,
      financialPotentialTotal: d.kpis.financial_potential_total,
      productOpportunities: d.kpis.product_opportunities,
      serviceOpportunities: d.kpis.service_opportunities,
      topVendor: d.kpis.top_vendor,
      topService: d.kpis.top_service,
    },
    vendorDistribution: pairs(d.vendor_distribution),
    financialByVendor: pairs(d.financial_by_vendor),
    opportunitiesByService: pairs(d.opportunities_by_service),
    customerVsProspect: [
      { label: 'Clientes', value: d.customer_vs_prospect.clientes },
      { label: 'Prospects', value: d.customer_vs_prospect.prospects },
    ],
    funnelCounts: d.funnel_counts,
  }
}

// ── Regras e catálogo (Fase C) ────────────────────────────────────────────────
// Espelham core/models.py direto (mesmo padrão de SourceStatus) — sem
// adaptador camelCase, é tela de configuração, não de resultado.

export interface Product {
  id: string
  vendor_id: string
  name: string
  category: string | null
}

export interface Service {
  id: string
  name: string
  category: string | null
}

export interface CorrelationRule {
  id: string
  opportunity_type: string
  justification: string
  requires: string[]
  absent: string[]
  requires_category: string[]
  absent_category: string[]
  relation_type: string | null
  active: boolean
}

export interface NewRule {
  opportunity_type: string
  justification: string
  requires?: string[]
  absent?: string[]
  requires_category?: string[]
  absent_category?: string[]
  relation_type?: string | null
}

export async function listProducts(): Promise<Product[]> {
  const resp = await fetch(`${BASE}/products`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

export async function listServices(): Promise<Service[]> {
  const resp = await fetch(`${BASE}/services`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

export async function listRules(): Promise<CorrelationRule[]> {
  const resp = await fetch(`${BASE}/rules`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

export async function createRule(rule: NewRule): Promise<CorrelationRule> {
  const resp = await fetch(`${BASE}/rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}
