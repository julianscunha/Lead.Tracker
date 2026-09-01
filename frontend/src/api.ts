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
