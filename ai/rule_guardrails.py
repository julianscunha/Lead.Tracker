"""Guardrail DETERMINÍSTICO sobre a sugestão de regras da IA. Função pura, sem I/O.

A IA só PROPÕE; a saída nunca é aceita pelo que diz. Uma sugestão só passa se:
  1. montar um `CorrelationRule` válido (um único mecanismo: item, categoria OU relação);
  2. todo id de requires/absent existir no catálogo ENVIADO e toda categoria casar (sem caixa/acento)
     com uma categoria dele — qualquer desconhecido descarta a sugestão inteira;
  3. nenhum item estiver em requires e absent ao mesmo tempo; item/categoria exigem condição positiva;
  4. a relação existir no catálogo (ao menos um ProductRelation daquele tipo);
  5. texto limpo (tamanho, sem markup/URL/caractere invisível).
Valor, scores, confiança e ativação vindos da IA são IGNORADOS (defaults do modelo; valor sempre None).
Duplicata de regra existente ou de outra sugestão não é sugerida. O descartado é só contado."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai.portfolio_guardrails import _norm, has_forbidden_chars
from core.models import CorrelationRule

MAX_RULE_SUGGESTIONS = 15
MAX_LIST = 10
_TYPE_RE = re.compile(r"^[\w -]+$")
_LINK_RE = re.compile(r"www\.|\b[a-z][a-z0-9+.-]*:|//|\b[a-z0-9-]+\.(?:com|net|org|io|br|app|dev)\b|<|>", re.IGNORECASE)


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    kind: str  # vendor | product | service
    vendor_name: str | None = None
    category: str | None = None
    relations: tuple[tuple[str, str], ...] = ()  # (service_id, relation_type)


@dataclass(frozen=True)
class RuleSuggestion:
    opportunity_type: str
    justification: str
    requires: list[str]
    absent: list[str]
    requires_category: list[str]
    absent_category: list[str]
    relation_type: str | None


def rule_signature(requires, absent, requires_category, absent_category, relation_type) -> tuple:
    mechanism = "relation" if relation_type else "category" if (requires_category or absent_category) else "item"
    return (
        mechanism, frozenset(requires), frozenset(absent),
        frozenset(_norm(c) for c in requires_category), frozenset(_norm(c) for c in absent_category), relation_type,
    )


def validate_rule_suggestions(
    raw_items: Any, catalog: list[CatalogItem], existing_rules: list[CorrelationRule],
) -> tuple[list[RuleSuggestion], int]:
    """(sugestões válidas, descartadas). `catalog` é exatamente o que foi enviado à IA."""
    if not isinstance(raw_items, list):
        return [], 0
    ids = {i.id for i in catalog}
    categories = {_norm(i.category): i.category for i in catalog if i.category}
    relations = {rt for i in catalog for _, rt in i.relations}
    seen = {rule_signature(r.requires, r.absent, r.requires_category, r.absent_category, r.relation_type)
            for r in existing_rules}
    accepted: list[RuleSuggestion] = []
    discarded = 0
    for raw in raw_items:
        suggestion = _validate_one(raw, ids, categories, relations)
        if suggestion is None:
            discarded += 1
            continue
        sig = rule_signature(suggestion.requires, suggestion.absent, suggestion.requires_category,
                             suggestion.absent_category, suggestion.relation_type)
        if sig in seen:
            continue  # já existe (ou já sugerida): repetição não é descarte relevante
        if len(accepted) >= MAX_RULE_SUGGESTIONS:
            discarded += 1
            continue
        seen.add(sig)
        accepted.append(suggestion)
    return accepted, discarded


def _str_list(value: Any) -> list[str] | None:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_LIST or not all(isinstance(v, str) for v in value):
        return None
    return list(dict.fromkeys(v.strip() for v in value if v.strip()))


def _clean_text(value: Any, low: int, high: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not low <= len(text) <= high or has_forbidden_chars(text) or _LINK_RE.search(text):
        return None
    return text


def _validate_one(raw: Any, ids: set[str], categories: dict[str, str], relations: set[str]) -> RuleSuggestion | None:
    if not isinstance(raw, dict):
        return None
    opp_type = _clean_text(raw.get("tipo_oportunidade"), 2, 40)
    justification = _clean_text(raw.get("justificativa"), 10, 300)
    if opp_type is None or justification is None or not _TYPE_RE.match(opp_type):
        return None
    requires, absent = _str_list(raw.get("requer")), _str_list(raw.get("ausente"))
    req_cat, abs_cat = _str_list(raw.get("requer_categoria")), _str_list(raw.get("ausente_categoria"))
    if None in (requires, absent, req_cat, abs_cat):
        return None
    if not all(i in ids for i in requires + absent) or set(requires) & set(absent):
        return None
    cats = []
    for c in req_cat + abs_cat:
        if _norm(c) not in categories:
            return None
        cats.append(categories[_norm(c)])  # reescreve com a grafia do catálogo
    req_cat, abs_cat = cats[:len(req_cat)], cats[len(req_cat):]
    relation = raw.get("relacao") or None
    if relation is not None and (not isinstance(relation, str) or relation not in relations):
        return None
    if not relation and not (requires or req_cat):
        return None  # só "ausente" geraria oportunidade para qualquer empresa
    try:  # reaproveita o validador do modelo: um único mecanismo de evidência, relation_type conhecido
        CorrelationRule(
            opportunity_type=opp_type, justification=justification, requires=requires, absent=absent,
            requires_category=req_cat, absent_category=abs_cat, relation_type=relation,
        )
    except Exception:  # noqa: BLE001 — qualquer recusa do modelo = descarte
        return None
    return RuleSuggestion(opp_type, justification, requires, absent, req_cat, abs_cat, relation)
