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
  scope_note: OpportunityRow['scopeNote']
  criticality: OpportunityRow['criticality']
  severity_note: string | null
  severity_band: OpportunityRow['severityBand']
  renewal_date: string | null
  account_health: OpportunityRow['accountHealth']
  qbr_suggested_days: number
  qbr_reason: string
  dismissal_reason: OpportunityRow['dismissalReason']
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
    companyId: r.company_id,
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
    scopeNote: r.scope_note,
    criticality: r.criticality,
    severityNote: r.severity_note,
    severityBand: r.severity_band,
    renewalDate: r.renewal_date,
    accountHealth: r.account_health,
    qbrSuggestedDays: r.qbr_suggested_days,
    qbrReason: r.qbr_reason,
    dismissalReason: r.dismissal_reason,
  }
}

export async function listOpportunities(): Promise<OpportunityRow[]> {
  const resp = await fetch(`${BASE}/opportunities`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const data: OpportunityApiRow[] = await resp.json()
  return data.map(fromApiRow)
}

export async function updateOpportunityQualification(
  id: string,
  qualification: { scopeNote: OpportunityRow['scopeNote']; criticality: OpportunityRow['criticality']; severityNote: string | null },
): Promise<OpportunityRow> {
  const resp = await fetch(`${BASE}/opportunities/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope_note: qualification.scopeNote,
      criticality: qualification.criticality,
      severity_note: qualification.severityNote,
    }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const data: OpportunityApiRow = await resp.json()
  return fromApiRow(data)
}

export async function updateOpportunityStatus(
  id: string,
  newStatus: OpportunityRow['status'],
  note: string | null,
  dismissalReason: OpportunityRow['dismissalReason'] = null,
): Promise<OpportunityRow> {
  const resp = await fetch(`${BASE}/opportunities/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_status: newStatus, note, dismissal_reason: dismissalReason }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const data: OpportunityApiRow = await resp.json()
  return fromApiRow(data)
}

export async function updateCompanyRenewalDate(companyId: string, renewalDate: string | null): Promise<void> {
  const resp = await fetch(`${BASE}/companies/${companyId}/renewal-date`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ renewal_date: renewalDate }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
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

export interface FunnelReachStage {
  stage: string
  reachCount: number
  reachRatioFromPrevious: number | null
}

export interface RepCoverage {
  repId: string
  actual: number
  target: number | null
  coverageRatio: number | null
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
  funnelReach: FunnelReachStage[]
  weightedPotential: { grossTotal: number; weightedEvaluatedTotal: number; weightedEstimatedTotal: number }
  potentialByRep: { label: string; value: number }[]
  potentialBySegment: { label: string; value: number }[]
  potentialBySource: { label: string; value: number }[]
  zombieCount: number
  agingCount: number
  agingSlaDays: number
  repCoverage: RepCoverage[]
  coveragePeriodType: PeriodType
  coveragePeriodKey: string
}

export async function getDashboardMetrics(periodType: PeriodType = 'monthly'): Promise<DashboardMetrics> {
  const resp = await fetch(`${BASE}/dashboard-metrics?period_type=${periodType}`)
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
    funnelReach: d.funnel_reach.map((r: { stage: string; reach_count: number; reach_ratio_from_previous: number | null }) => ({
      stage: r.stage, reachCount: r.reach_count, reachRatioFromPrevious: r.reach_ratio_from_previous,
    })),
    weightedPotential: {
      grossTotal: d.weighted_potential.gross_total,
      weightedEvaluatedTotal: d.weighted_potential.weighted_evaluated_total,
      weightedEstimatedTotal: d.weighted_potential.weighted_estimated_total,
    },
    potentialByRep: pairs(d.potential_by_rep),
    potentialBySegment: pairs(d.potential_by_segment),
    potentialBySource: pairs(d.potential_by_source),
    zombieCount: d.zombie_count,
    agingCount: d.aging_count,
    agingSlaDays: d.aging_sla_days,
    repCoverage: d.rep_coverage.map((c: { rep_id: string; actual: number; target: number | null; coverage_ratio: number | null }) => ({
      repId: c.rep_id, actual: c.actual, target: c.target, coverageRatio: c.coverage_ratio,
    })),
    coveragePeriodType: d.coverage_period_type,
    coveragePeriodKey: d.coverage_period_key,
  }
}

// ── Prospecção geográfica (Fase E) ────────────────────────────────────────────

export interface ICPProfileData {
  referenceProductId: string | null
  placeCategory: string | null
  companySizeHint: string | null
  radiusKm: number | null
  searchOriginAddress: string | null
}

function icpProfileFromApi(d: {
  reference_product_id: string | null; place_category: string | null; company_size_hint: string | null
  radius_km: number | null; search_origin_address: string | null
}): ICPProfileData {
  return {
    referenceProductId: d.reference_product_id, placeCategory: d.place_category,
    companySizeHint: d.company_size_hint, radiusKm: d.radius_km, searchOriginAddress: d.search_origin_address,
  }
}

export async function getIcpProfile(): Promise<ICPProfileData> {
  const resp = await fetch(`${BASE}/icp-profile`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return icpProfileFromApi(await resp.json())
}

export async function updateIcpProfile(profile: ICPProfileData): Promise<ICPProfileData> {
  const resp = await fetch(`${BASE}/icp-profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reference_product_id: profile.referenceProductId, place_category: profile.placeCategory,
      company_size_hint: profile.companySizeHint, radius_km: profile.radiusKm,
      search_origin_address: profile.searchOriginAddress,
    }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return icpProfileFromApi(await resp.json())
}

export interface ICPSuggestion {
  industryHint: string | null
  industryHintShare: number | null
  companySizeHint: string | null
  companySizeHintShare: number | null
  sampleSize: number
  confidence: 'low' | 'high'
}

export async function getIcpSuggestion(): Promise<ICPSuggestion | null> {
  const resp = await fetch(`${BASE}/icp-suggestion`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const d = await resp.json()
  if (d === null) return null
  return {
    industryHint: d.industry_hint, industryHintShare: d.industry_hint_share,
    companySizeHint: d.company_size_hint, companySizeHintShare: d.company_size_hint_share,
    sampleSize: d.sample_size, confidence: d.confidence,
  }
}

export interface GeoDiscoveryRequest {
  repId: string
  referenceProductId: string | null
  searchOriginAddress: string
  radiusKm: number
  placeCategory: string | null
  companySizeHint: string | null
}

export interface GeoDiscoveryItem {
  placeId: string
  name: string
  category: string | null
  categoryMatches: boolean
  rating: number | null
  reviewCount: number
  formattedAddress: string | null
  score: number | null
  companyId: string | null
  opportunityId: string | null
}

export interface GeoDiscoveryResult {
  promoted: GeoDiscoveryItem[]
  deferred: GeoDiscoveryItem[]
  rejected: GeoDiscoveryItem[]
}

interface GeoDiscoveryItemApi {
  place_id: string; name: string; category: string | null; category_matches: boolean
  rating: number | null; review_count: number; formatted_address: string | null; score: number | null
  company_id: string | null; opportunity_id: string | null
}

function geoDiscoveryItemFromApi(d: GeoDiscoveryItemApi): GeoDiscoveryItem {
  return {
    placeId: d.place_id, name: d.name, category: d.category, categoryMatches: d.category_matches,
    rating: d.rating, reviewCount: d.review_count, formattedAddress: d.formatted_address, score: d.score,
    companyId: d.company_id, opportunityId: d.opportunity_id,
  }
}

export async function runGeoDiscovery(request: GeoDiscoveryRequest): Promise<GeoDiscoveryResult> {
  const resp = await fetch(`${BASE}/geo-discovery/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      rep_id: request.repId, reference_product_id: request.referenceProductId,
      search_origin_address: request.searchOriginAddress, radius_km: request.radiusKm,
      place_category: request.placeCategory, company_size_hint: request.companySizeHint,
    }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const d = await resp.json()
  return {
    promoted: d.promoted.map(geoDiscoveryItemFromApi),
    deferred: d.deferred.map(geoDiscoveryItemFromApi),
    rejected: d.rejected.map(geoDiscoveryItemFromApi),
  }
}

// Fase E, módulo 8 (`geo-export`) — reaproveita /exports/pdf e /exports/excel
// já existentes (módulo genérico de Oportunidades), sem exportador novo.
// `priority` (campo livre no schema de exportação) carrega o rótulo do grupo
// comercial em vez de uma prioridade real — ponytail: título/colunas do PDF
// seguem o template fixo "Oportunidades" (nenhum código de exportação é
// específico de prospecção); aceitável porque reaproveitar é o objetivo
// explícito deste módulo, upgrade só se o rótulo genérico confundir na prática.
function toGeoExportRow(item: GeoDiscoveryItem, groupLabel: string) {
  return {
    company_name: item.name,
    is_customer: false,
    opportunity_score: item.score,
    financial_potential: null,
    product: null,
    service: item.category,
    priority: groupLabel,
    sources: ['google_maps'],
  }
}

function geoDiscoveryExportRows(result: GeoDiscoveryResult) {
  return [
    ...result.promoted.map(i => toGeoExportRow(i, 'Pronto para contato')),
    ...result.deferred.map(i => toGeoExportRow(i, 'Fila para amanhã')),
    ...result.rejected.map(i => toGeoExportRow(i, 'Fora do critério')),
  ]
}

export async function exportGeoDiscoveryPdf(result: GeoDiscoveryResult, filtersSummary: string): Promise<void> {
  const resp = await fetch(`${BASE}/exports/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: geoDiscoveryExportRows(result), filters_summary: filtersSummary }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  downloadBlob(await resp.blob(), 'prospeccao-geografica.pdf')
}

export async function exportGeoDiscoveryExcel(result: GeoDiscoveryResult): Promise<void> {
  const resp = await fetch(`${BASE}/exports/excel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: geoDiscoveryExportRows(result) }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  downloadBlob(await resp.blob(), 'prospeccao-geografica.xlsx')
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

export type PeriodType = 'monthly' | 'quarterly'

export interface RepTarget {
  rep_id: string
  period_type: PeriodType
  period_key: string
  target_amount: number
}

export async function listRepTargets(periodType: PeriodType, periodKey: string): Promise<RepTarget[]> {
  const resp = await fetch(`${BASE}/rep-targets?period_type=${periodType}&period_key=${encodeURIComponent(periodKey)}`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

export async function createRepTarget(target: RepTarget): Promise<RepTarget> {
  const resp = await fetch(`${BASE}/rep-targets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(target),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  return resp.json()
}

// ── Mapeamento de campo personalizado (Fase F) ──────────────────────────────
// Só Salesforce tem catálogo/mapeamento nesta fase — mesma convenção do
// backend (provider_id fixo na rota, não no core).
export type SemanticFieldRole = 'industry_hint' | 'deal_size_hint' | 'renewal_date'

export interface FieldCatalogItem {
  sourceFieldApiName: string
  sourceFieldLabel: string
  fieldType: string
  role: SemanticFieldRole | null
}

interface FieldCatalogItemApi {
  source_field_api_name: string
  source_field_label: string
  field_type: string
  role: SemanticFieldRole | null
}

export async function getFieldCatalog(forceRefresh = false): Promise<FieldCatalogItem[]> {
  const resp = await fetch(`${BASE}/settings/salesforce/field-catalog?force_refresh=${forceRefresh}`)
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const data: FieldCatalogItemApi[] = await resp.json()
  return data.map(d => ({
    sourceFieldApiName: d.source_field_api_name, sourceFieldLabel: d.source_field_label,
    fieldType: d.field_type, role: d.role,
  }))
}

export async function upsertFieldMapping(
  apiName: string, label: string, role: SemanticFieldRole,
): Promise<{ reassignedFromApiName: string | null; reassignedFromLabel: string | null }> {
  const resp = await fetch(`${BASE}/settings/salesforce/field-mapping`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_field_api_name: apiName, source_field_label: label, role }),
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
  const data = await resp.json()
  // reassignedFromApiName é o identificador estável pra reconciliar estado
  // local — reassignedFromLabel só compõe a frase do toast (dois campos
  // com o mesmo rótulo numa org mal configurada não podem depender do
  // rótulo pra decidir qual linha perdeu o papel; achado de revisão de código).
  return { reassignedFromApiName: data.reassigned_from_api_name, reassignedFromLabel: data.reassigned_from_label }
}

export async function unmapField(apiName: string): Promise<void> {
  const resp = await fetch(`${BASE}/settings/salesforce/field-mapping/${encodeURIComponent(apiName)}`, {
    method: 'DELETE',
  })
  if (!resp.ok) throw new Error(await friendlyError(resp))
}
