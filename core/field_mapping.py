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
