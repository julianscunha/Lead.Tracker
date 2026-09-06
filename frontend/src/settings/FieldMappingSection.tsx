import { useEffect, useState } from 'react'
import { getFieldCatalog, unmapField, upsertFieldMapping, type FieldCatalogItem, type SemanticFieldRole } from '../api'

// Fase F, módulo 5 (`mapping-config-ui`) — decisões de linguagem/UX em
// consulta ao agente Sales Engineer (docs/specs/
// fase-f-mapeamento-campo-personalizado.md, módulo 5): nunca "hint"/termo
// técnico visível, coluna "status" colapsada no próprio dropdown de papel,
// campo não mapeado não precisa de nenhuma explicação por linha (silêncio
// é a resposta certa), reatribuição de papel é automática com aviso curto
// em vez de bloquear a ação.
const ROLE_LABEL: Record<SemanticFieldRole, string> = {
  industry_hint: 'Setor / segmento do cliente',
  deal_size_hint: 'Porte estimado do negócio',
  renewal_date: 'Data de renovação do contrato',
}

export function FieldMappingSection() {
  const [fields, setFields] = useState<FieldCatalogItem[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [savingField, setSavingField] = useState<string | null>(null)

  useEffect(() => {
    getFieldCatalog()
      .then(setFields)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Não consegui carregar os campos do Salesforce.'))
  }, [])

  const handleRoleChange = async (field: FieldCatalogItem, role: SemanticFieldRole | '') => {
    setSavingField(field.sourceFieldApiName)
    setMessage(null)
    try {
      if (role === '') {
        await unmapField(field.sourceFieldApiName)
        setFields(prev => prev!.map(f => (f.sourceFieldApiName === field.sourceFieldApiName ? { ...f, role: null } : f)))
      } else {
        const { reassignedFromApiName, reassignedFromLabel } = await upsertFieldMapping(
          field.sourceFieldApiName, field.sourceFieldLabel, role,
        )
        setFields(prev => prev!.map(f => {
          if (f.sourceFieldApiName === field.sourceFieldApiName) return { ...f, role }
          // Reconcilia por api_name, nunca por rótulo — dois campos podem
          // compartilhar o mesmo rótulo numa org Salesforce mal configurada
          // (achado de revisão de código).
          if (reassignedFromApiName && f.sourceFieldApiName === reassignedFromApiName) return { ...f, role: null }
          return f
        }))
        setMessage(
          reassignedFromLabel
            ? `${ROLE_LABEL[role]} agora é preenchido por ${field.sourceFieldLabel} em vez de ${reassignedFromLabel}.`
            : `A partir de agora, o valor de ${field.sourceFieldLabel} será a fonte de verdade para ${ROLE_LABEL[role]} — ele substitui qualquer valor que o sistema já tenha.`,
        )
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Falha ao atualizar o mapeamento.')
    } finally {
      setSavingField(null)
    }
  }

  if (loadError) return <p className="lt-hint" role="alert">{loadError}</p>
  if (!fields) return <p className="lt-hint">Carregando campos do Salesforce…</p>

  const sorted = [...fields].sort((a, b) => (a.role === b.role ? 0 : a.role ? -1 : 1))

  return (
    <div>
      <div className="lt-header">
        <h2>Mapeamento de campos do Salesforce</h2>
        <p>
          Alguns campos personalizados do Salesforce podem preencher automaticamente informações do sistema. Campos
          que você não mapear continuam sendo considerados pela IA normalmente.
        </p>
      </div>
      {message && <p className="lt-hint" role="status">{message}</p>}

      {sorted.length === 0 ? (
        <p className="lt-empty" role="status">Nenhum campo personalizado encontrado no Salesforce.</p>
      ) : (
        <table className="lt-table">
          <thead>
            <tr><th>Campo do Salesforce</th><th>Preenche este dado do sistema</th></tr>
          </thead>
          <tbody>
            {sorted.map(f => (
              <tr key={f.sourceFieldApiName}>
                <td>{f.sourceFieldLabel}</td>
                <td>
                  <select
                    value={f.role ?? ''}
                    disabled={savingField === f.sourceFieldApiName}
                    onChange={e => handleRoleChange(f, e.target.value as SemanticFieldRole | '')}
                  >
                    <option value="">—</option>
                    {(Object.keys(ROLE_LABEL) as SemanticFieldRole[]).map(role => (
                      <option key={role} value={role}>{ROLE_LABEL[role]}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
