"""Fase P — sugestão de portfólio a partir do site da própria empresa (COMPANY_WEBSITE).

`POST /portfolio-suggestions` lê o site (coleta segura), pede sugestões à IA e valida cada uma contra o
texto coletado; NADA é gravado. `POST /portfolio-suggestions/apply` cria só os itens que o operador marcou,
pelos mesmos modelos do cadastro manual. Sem IA configurada não há sugestão (o cadastro manual segue)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ai.base import AIProviderError
from ai.factory import create_ai_provider
from ai.portfolio_extract import suggest_portfolio
from ai.portfolio_guardrails import MAX_NAME, MAX_SUGGESTIONS, _NAME_FORBIDDEN
from backend import routes_settings
from backend.db_session import session_factory
from backend.http_errors import raise_http
from core.config import load_env
from core.errors import DomainError, ErrorCategory
from core.models import Product, Service, Vendor
from core.normalization import catalog_key
from core.repository import list_products, list_services, list_vendors, save_product, save_service, save_vendor
from providers.base import ProviderError
from providers.website import WebsiteProvider

router = APIRouter(tags=["lead_tracker-portfolio-suggest"])


class SuggestionOut(BaseModel):
    kind: Literal["vendor", "product", "service"]
    name: str
    vendor_name: str | None
    evidence: str
    page_url: str
    already_in_catalog: bool


class SuggestionsOut(BaseModel):
    suggestions: list[SuggestionOut]
    discarded: int
    pages_read: int


class ApplyItem(BaseModel):
    kind: Literal["vendor", "product", "service"]
    name: str = Field(min_length=2, max_length=MAX_NAME)
    vendor_name: str | None = Field(default=None, max_length=MAX_NAME)


class ApplyIn(BaseModel):
    items: list[ApplyItem] = Field(min_length=1, max_length=MAX_SUGGESTIONS)


class ApplyOut(BaseModel):
    created: dict[str, int]
    skipped_existing: int


def _catalog_index(vendors, products, services) -> dict[str, set[str]]:
    return {
        "vendor": {catalog_key(v.name) for v in vendors},
        "product": {catalog_key(n) for p in products for n in [p.name, *p.aliases]},
        "service": {catalog_key(s.name) for s in services},
    }


@router.post("/portfolio-suggestions")
async def suggest_from_website() -> SuggestionsOut:
    env = load_env(routes_settings._ENV_PATH)
    api_key = env.get("AI_API_KEY", "")
    if not api_key:
        raise_http(DomainError(
            ErrorCategory.CONFIGURATION,
            "Para sugerir o portfólio a partir do site é preciso configurar um provedor de IA.",
            "Configure a chave de IA em Configurações; enquanto isso, cadastre o portfólio manualmente.",
        ))
    try:
        site = WebsiteProvider(env.get("COMPANY_WEBSITE", ""))  # revalida a URL AGORA, não confia no valor salvo
        pages = await site.collect_pages()
        provider = create_ai_provider(env.get("AI_PROVIDER", ""), api_key, env.get("AI_MODEL", ""))
        suggestions, discarded = await suggest_portfolio(provider, pages)
    except (ProviderError, AIProviderError, DomainError) as exc:
        raise_http(exc)
    async with session_factory() as session:
        index = _catalog_index(await list_vendors(session), await list_products(session), await list_services(session))
    return SuggestionsOut(
        suggestions=[
            SuggestionOut(
                kind=s.kind, name=s.name, vendor_name=s.vendor_name, evidence=s.evidence, page_url=s.page_url,
                already_in_catalog=catalog_key(s.name) in index[s.kind],
            )
            for s in suggestions
        ],
        discarded=discarded, pages_read=len(pages),
    )


def _reject_markup(*values: str | None) -> None:
    if any(v and _NAME_FORBIDDEN.search(v) for v in values):
        raise_http(DomainError(ErrorCategory.INVALID_DATA, "Há um nome inválido na seleção.", "Revise os itens marcados."))


@router.post("/portfolio-suggestions/apply")
async def apply_suggestions(body: ApplyIn) -> ApplyOut:
    """Cria só o que o operador marcou; o que já existe no catálogo é ignorado (nunca duplica nem sobrescreve)."""
    for item in body.items:
        _reject_markup(item.name, item.vendor_name)
        if item.kind == "product" and not (item.vendor_name or "").strip():
            raise_http(DomainError(
                ErrorCategory.INVALID_DATA, f"O produto \"{item.name}\" precisa de um fabricante.",
                "Escolha o fabricante ou troque o item para serviço.",
            ))
    created = {"vendor": 0, "product": 0, "service": 0}
    skipped = 0
    async with session_factory() as session:
        vendors = {catalog_key(v.name): v for v in await list_vendors(session)}
        products = {catalog_key(n) for p in await list_products(session) for n in [p.name, *p.aliases]}
        services = {catalog_key(s.name) for s in await list_services(session)}
        for item in body.items:
            name = " ".join(item.name.split())
            key = catalog_key(name)
            if item.kind == "vendor":
                if key in vendors:
                    skipped += 1
                    continue
                vendors[key] = Vendor(name=name)
                await save_vendor(session, vendors[key])
                created["vendor"] += 1
            elif item.kind == "service":
                if key in services:
                    skipped += 1
                    continue
                services.add(key)
                await save_service(session, Service(name=name))
                created["service"] += 1
            else:
                if key in products:
                    skipped += 1
                    continue
                vendor_name = " ".join((item.vendor_name or "").split())
                vendor = vendors.get(catalog_key(vendor_name))
                if vendor is None:
                    vendor = Vendor(name=vendor_name)
                    vendors[catalog_key(vendor_name)] = vendor
                    await save_vendor(session, vendor)
                    created["vendor"] += 1
                products.add(key)
                await save_product(session, Product(vendor_id=vendor.id, name=name))
                created["product"] += 1
    return ApplyOut(created=created, skipped_existing=skipped)
