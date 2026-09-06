"""
Fase F, módulo 4 (`mapping-driven-context-split`) — divide o contexto bruto
de um provider entre campo estrutural (quando existe `FieldMapping` pro
papel) e contexto que continua bruto pra IA (quando não existe). Puro: não
sabe nada de SQL/sessão nem de Salesforce especificamente — `providers/
salesforce.py::fetch_context()` já entrega o dict genérico, quem decide como
persistir é `core/repository.py`.

Precedência (Salesforce Architect consultado, docs/specs/
fase-f-mapeamento-campo-personalizado.md): campo mapeado sempre sobrescreve
o campo estrutural correspondente, nunca "só se vazio" — é o usuário
escolhendo explicitamente aquele campo customizado como fonte de verdade
pro papel, não um merge implícito entre fontes conflitantes (mesma
diferença de core/normalization.py::merge_pair, que resolve conflito
IMPLÍCITO entre duas fontes que nunca foram configuradas uma contra a
outra).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.models import FieldMapping, SemanticFieldRole

_ROLE_TO_COMPANY_FIELD: dict[SemanticFieldRole, str] = {
    SemanticFieldRole.INDUSTRY_HINT: "industry",
    SemanticFieldRole.DEAL_SIZE_HINT: "deal_size_hint",
    SemanticFieldRole.RENEWAL_DATE: "renewal_date",
}


def _parse_role_value(role: SemanticFieldRole, value: Any) -> Any | None:
    """Nunca derruba o sync por um valor inesperado — valor que não parseia
    pro tipo do papel fica de fora do update, nunca vira exceção crua
    (CLAUDE.md 'Error handling & resilience')."""
    if role == SemanticFieldRole.RENEWAL_DATE:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None
    if role == SemanticFieldRole.DEAL_SIZE_HINT:
        if isinstance(value, bool):  # bool é subclasse de int — nunca aceitar como número
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None
    if role == SemanticFieldRole.INDUSTRY_HINT:
        return value if isinstance(value, str) and value else None
    return None


def split_custom_fields(
    custom_fields: dict[str, Any], mappings: list[FieldMapping],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Devolve `(column_updates, remaining_raw_context)`.

    `column_updates` só tem entrada pra papel com valor parseável de
    verdade — um valor vazio/inválido não escreve lixo no campo estrutural.
    Mesmo assim o campo some de `remaining_raw_context` sempre que está
    mapeado (com valor válido ou não): é a CONFIGURAÇÃO de mapeamento, não
    o valor de uma empresa em particular, que decide se aquele campo é
    "estrutural" a partir de agora — evita a mesma empresa mostrar o campo
    como estruturado hoje e como contexto bruto amanhã só porque o valor
    momentaneamente veio vazio (Salesforce Architect consultado)."""
    remaining = dict(custom_fields)
    updates: dict[str, Any] = {}
    for mapping in mappings:
        if mapping.source_field_api_name not in remaining:
            continue
        raw_value = remaining.pop(mapping.source_field_api_name)
        parsed = _parse_role_value(mapping.role, raw_value)
        if parsed is not None:
            updates[_ROLE_TO_COMPANY_FIELD[mapping.role]] = parsed
    return updates, remaining


# Fase F, módulo 6 (`mapping-health-check`) — Sales Engineer consultado
# (docs/specs/fase-f-mapeamento-campo-personalizado.md): só detecta campo
# REMOVIDO do catálogo (nunca importa `providers/salesforce.py` aqui — o
# chamador, que já tem permissão de importar provider, passa só os nomes de
# campo do catálogo atual, um `set[str]` puro). Mudança de TIPO do campo
# (mantendo o nome) fica fora do escopo desta fatia — exigiria guardar o
# tipo original no `FieldMapping` no momento do mapeamento, schema novo não
# justificado ainda pra um aviso "mais brando" que o próprio Sales Engineer
# tratou como opcional.
ROLE_LABEL_PT: dict[SemanticFieldRole, str] = {
    SemanticFieldRole.INDUSTRY_HINT: "Setor / segmento do cliente",
    SemanticFieldRole.DEAL_SIZE_HINT: "Porte estimado do negócio",
    SemanticFieldRole.RENEWAL_DATE: "Data de renovação do contrato",
}


@dataclass
class BrokenFieldMapping:
    source_field_api_name: str
    source_field_label: str
    role: SemanticFieldRole

    def business_message(self) -> str:
        """Frase exata definida em consulta ao Sales Engineer — nunca
        jargão de API ("not found", nome técnico do campo), sempre o papel
        de negócio e a ação seguinte."""
        role_label = ROLE_LABEL_PT[self.role]
        return (
            f"O campo que alimenta \"{role_label}\" foi removido ou renomeado no Salesforce e parou de ser "
            "atualizado. Isso não é um erro do Lead.Tracker — foi uma alteração feita direto no Salesforce. "
            "Vá em Configurações > Mapeamento de Campos e escolha um novo campo para continuar recebendo essa "
            "informação."
        )


def detect_broken_mappings(mappings: list[FieldMapping], catalog_field_names: set[str]) -> list[BrokenFieldMapping]:
    """Compara mapeamentos salvos contra o catálogo ATUAL de campos — campo
    mapeado que sumiu do catálogo (removido/renomeado no Salesforce, fora
    do controle do Lead.Tracker) vira um aviso, nunca falha silenciosa."""
    return [
        BrokenFieldMapping(
            source_field_api_name=m.source_field_api_name, source_field_label=m.source_field_label, role=m.role,
        )
        for m in mappings
        if m.source_field_api_name not in catalog_field_names
    ]
