// Espelha core/models.py (Company + Opportunity) — só os campos que a
// tela de Oportunidades usa. Sem endpoint real ainda: a
// persistência/API de listagem não existe até a integração ser fiada
//. Por ora a tela recebe os dados prontos via prop.

export type OpportunityStatus =
  | 'detected' | 'qualified' | 'reviewed' | 'contacted' | 'opportunity' | 'dismissed'

export interface SourceRef {
  type: string
  confidence: number
}

export interface OpportunityRow {
  id: string
  companyName: string
  isCustomer: boolean
  opportunityScore: number | null
  financialPotential: number | null
  type: string
  product: string | null
  service: string | null
  priority: 'alta' | 'média' | 'baixa'
  sources: SourceRef[]
  status: OpportunityStatus
  evidence: string[]
  justification: string | null
  confidenceScore: number | null
  currentProducts: string[]
  recommendedProducts: string[]
  recommendedServices: string[]
}

export type SortKey = 'score' | 'potencial' | 'prioridade' | 'confianca'
export type ClientFilter = 'todos' | 'clientes' | 'prospects'
