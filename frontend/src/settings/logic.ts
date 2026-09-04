import type { SourceStatus } from '../api'

/** Decide se o toggle deve abrir o formulário de credencial (falta valor
 * obrigatório) ou já pode tentar conectar direto. Lógica pura, sem estado —
 * o componente só chama isso e reage ao resultado. */
export function needsCredentialsBeforeEnabling(source: SourceStatus): boolean {
  return source.fields.some(f => !f.has_value)
}
