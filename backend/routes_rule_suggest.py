"""Sugestão de regras pela IA a partir do portfólio. `POST /rule-suggestions` NÃO grava nada: devolve cartões
validados (`ai/rule_guardrails.py`); o operador aceita um a um pelo `POST /rules` do cadastro manual.
Sem IA configurada não há sugestão (a regra manual segue funcionando)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from ai.base import AIProviderError
from ai.factory import create_ai_provider
from ai.rule_suggest import suggest_rules
from backend import routes_settings
from backend.db_session import session_factory
from backend.http_errors import raise_http
from core.config import load_env
from core.errors import DomainError, ErrorCategory
from core.repository import list_products, list_rules, list_services, list_vendors

router = APIRouter(tags=["lead_tracker-rule-suggest"])


class RuleSuggestionOut(BaseModel):
    opportunity_type: str
    justification: str
    requires: list[str]
    absent: list[str]
    requires_category: list[str]
    absent_category: list[str]
    relation_type: str | None
    requires_labels: list[str]
    absent_labels: list[str]


class RuleSuggestionsOut(BaseModel):
    suggestions: list[RuleSuggestionOut]
    discarded: int


_IN_FLIGHT = asyncio.Lock()  # uma chamada de IA por vez: cliques repetidos não multiplicam o gasto


@router.post("/rule-suggestions")
async def suggest_rules_route() -> RuleSuggestionsOut:
    if _IN_FLIGHT.locked():
        raise_http(DomainError(ErrorCategory.API_LIMIT, "Já há uma sugestão em andamento.", "Aguarde terminar e tente de novo."))
    async with _IN_FLIGHT:
        return await _suggest()


async def _suggest() -> RuleSuggestionsOut:
    env = load_env(routes_settings._ENV_PATH)
    api_key = env.get("AI_API_KEY", "")
    if not api_key:
        raise_http(DomainError(
            ErrorCategory.CONFIGURATION,
            "Para sugerir regras é preciso configurar um provedor de IA.",
            "Configure a chave de IA em Configurações; enquanto isso, crie as regras manualmente (Nova regra).",
        ))
    async with session_factory() as session:
        vendors, products = await list_vendors(session), await list_products(session)
        services, existing = await list_services(session), await list_rules(session)
    try:
        provider = create_ai_provider(env.get("AI_PROVIDER", ""), api_key, env.get("AI_MODEL", ""))
        suggestions, discarded, catalog = await suggest_rules(provider, vendors, products, services, existing)
    except (AIProviderError, DomainError) as exc:
        raise_http(exc)
    names = {i.id: i.name for i in catalog}
    return RuleSuggestionsOut(
        suggestions=[
            RuleSuggestionOut(
                opportunity_type=s.opportunity_type, justification=s.justification, requires=s.requires,
                absent=s.absent, requires_category=s.requires_category, absent_category=s.absent_category,
                relation_type=s.relation_type,
                requires_labels=[names[i] for i in s.requires], absent_labels=[names[i] for i in s.absent],
            )
            for s in suggestions
        ],
        discarded=discarded,
    )
