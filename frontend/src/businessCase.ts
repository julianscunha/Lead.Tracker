import type { OpportunityRow } from './types'

export type ProseSource = 'ia' | 'mista' | 'deterministica' | 'desconhecida'

export function canExportBusinessCase(row: Pick<OpportunityRow, 'evidence' | 'product' | 'service'>): { enabled: boolean; reason: string | null } {
  if (!row.product && !row.service) {
    return {
      enabled: false,
      reason: 'Esta oportunidade ainda não está ligada a um produto ou serviço do portfólio; sem isso não é possível montar o business case.',
    }
  }
  if (row.evidence.length === 0) {
    return {
      enabled: false,
      reason: 'Esta oportunidade ainda não tem evidências registradas; sem elas não é possível montar o business case.',
    }
  }
  return { enabled: true, reason: null }
}

export function businessCaseFileName(name: string, date: Date): string {
  const slug = name
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
    .slice(0, 40).replace(/-+$/, '') || 'oportunidade'
  const p = (n: number) => String(n).padStart(2, '0')
  return `business-case-${slug}-${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}.pdf`
}

export function parseProseSource(header: string | null): ProseSource {
  return header === 'ia' || header === 'mista' || header === 'deterministica' ? header : 'desconhecida'
}

const REVIEW = 'Rascunho para revisão do vendedor.'

export function proseSourceMessage(fonte: ProseSource, usouIa: boolean): string {
  if (fonte === 'ia') return `Texto melhorado por IA. ${REVIEW}`
  if (fonte === 'mista') return `Texto parcialmente melhorado por IA; o restante usa o texto padrão. ${REVIEW}`
  if (fonte === 'desconhecida') return usouIa ? `Business case baixado. Não foi possível confirmar se a IA foi usada. ${REVIEW}` : `Business case baixado. ${REVIEW}`
  return usouIa ? `Texto padrão usado (IA indisponível). ${REVIEW}` : `Business case baixado. ${REVIEW}`
}
