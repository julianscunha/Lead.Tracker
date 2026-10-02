import { afterEach, describe, expect, it, vi } from 'vitest'
import { exportBusinessCase } from './api'
import { businessCaseFileName, canExportBusinessCase, parseProseSource, proseSourceMessage } from './businessCase'
import { sampleOpportunities } from './sampleData'

describe('canExportBusinessCase', () => {
  it('desabilita sem evidências, com motivo', () => {
    const r = canExportBusinessCase({ ...sampleOpportunities[0], product: 'P', evidence: [] })
    expect(r.enabled).toBe(false)
    expect(r.reason).toContain('ainda não tem evidências')
  })
  it('habilita com evidência', () => {
    expect(canExportBusinessCase({ ...sampleOpportunities[0], evidence: ['fato'] })).toEqual({ enabled: true, reason: null })
  })
  it('desabilita sem produto e sem serviço, só com o motivo do item', () => {
    const r = canExportBusinessCase({ ...sampleOpportunities[0], product: null, service: null, evidence: [] })
    expect(r).toEqual({ enabled: false, reason: 'Esta oportunidade ainda não está ligada a um produto ou serviço do portfólio; sem isso não é possível montar o business case.' })
  })
  it('habilita só com produto ou só com serviço', () => {
    expect(canExportBusinessCase({ ...sampleOpportunities[0], product: 'P', service: null, evidence: ['f'] }).enabled).toBe(true)
    expect(canExportBusinessCase({ ...sampleOpportunities[0], product: null, service: 'S', evidence: ['f'] }).enabled).toBe(true)
  })
})

describe('businessCaseFileName', () => {
  it('remove acentos e símbolos', () => {
    expect(businessCaseFileName('Ação Ótima S/A', new Date(2026, 9, 1))).toBe('business-case-acao-otima-s-a-2026-10-01.pdf')
  })
  it('usa fallback para nome vazio ou só símbolos', () => {
    expect(businessCaseFileName('', new Date(2026, 9, 1))).toBe('business-case-oportunidade-2026-10-01.pdf')
    expect(businessCaseFileName('///', new Date(2026, 9, 1))).toBe('business-case-oportunidade-2026-10-01.pdf')
  })
  it('limita o tamanho do slug', () => {
    expect(businessCaseFileName('a'.repeat(200), new Date(2026, 9, 1)).length).toBeLessThan(70)
  })
})

describe('parseProseSource', () => {
  it('aceita valores válidos', () => {
    for (const v of ['ia', 'mista', 'deterministica'] as const) expect(parseProseSource(v)).toBe(v)
  })
  it('inválido ou ausente vira desconhecida, sem lançar', () => {
    for (const v of [null, 'xyz', '']) expect(parseProseSource(v)).toBe('desconhecida')
  })
})

describe('proseSourceMessage', () => {
  it('deterministica com IA pedida avisa indisponibilidade', () => {
    expect(proseSourceMessage('deterministica', true)).toContain('IA indisponível')
  })
  it('deterministica sem IA não menciona IA', () => {
    expect(proseSourceMessage('deterministica', false)).not.toMatch(/\bIA\b/)
  })
  it('desconhecida com IA não afirma indisponibilidade nem melhoria', () => {
    const m = proseSourceMessage('desconhecida', true)
    expect(m).toContain('Não foi possível confirmar se a IA foi usada')
    expect(m).not.toContain('IA indisponível')
    expect(m).not.toContain('melhorado por IA')
  })
  it('desconhecida sem IA não menciona IA', () => {
    expect(proseSourceMessage('desconhecida', false)).toBe('Business case baixado. Rascunho para revisão do vendedor.')
  })
  it('ia e mista são distintas e pedem revisão', () => {
    expect(proseSourceMessage('ia', true)).not.toBe(proseSourceMessage('mista', true))
    for (const f of ['ia', 'mista', 'deterministica', 'desconhecida'] as const)
      for (const u of [true, false]) {
        const m = proseSourceMessage(f, u)
        expect(m).toContain('revisão do vendedor')
        expect(m).not.toMatch(/chance|probabilidade|valor|receita/i)
      }
  })
})

describe('exportBusinessCase', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('envia só opportunity_id e usar_ia e baixa com o nome certo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(['%PDF']), { status: 200, headers: { 'X-Prosa-Fonte': 'mista' } }))
    vi.stubGlobal('fetch', fetchMock)
    const click = vi.fn()
    const a: { href?: string; download?: string; click: () => void } = { click }
    vi.stubGlobal('document', { createElement: () => a })
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })
    const r = await exportBusinessCase('opp-1', true, 'Acme')
    expect(r).toEqual({ fonte: 'mista' })
    expect(Object.keys(JSON.parse(fetchMock.mock.calls[0][1].body)).sort()).toEqual(['opportunity_id', 'usar_ia'])
    expect(a.download).toMatch(/^business-case-acme-\d{4}-\d{2}-\d{2}\.pdf$/)
    expect(click).toHaveBeenCalled()
  })
  it('sem cabeçalho trata como desconhecida', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Blob(['%PDF']), { status: 200 })))
    vi.stubGlobal('document', { createElement: () => ({ click() {} }) })
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })
    expect(await exportBusinessCase('o', false, 'X')).toEqual({ fonte: 'desconhecida' })
  })
  it('erro de rede vira mensagem amigável', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(exportBusinessCase('o', false, 'X')).rejects.toThrow('Não foi possível conectar ao módulo. Tente novamente.')
  })
})
