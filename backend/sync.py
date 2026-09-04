"""
Orquestração de sincronização (Fase B.1/C do roadmap): aciona os providers
habilitados, normaliza, persiste companies/contacts de verdade, e roda o
motor de regras (Fase C) contra o portfólio já conhecido de cada empresa.
Empresa sem portfólio (Portfolio) cadastrado não gera oportunidade nenhuma
— não é bug, é honesto: não existe ainda fonte que popule "o que o cliente
tem" a partir de Salesforce/Manual (ver docs/specs/fase-b1-ligacao-real.md).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.settings import SOURCES, SourceDescriptor
from core.models import Company
from core.normalization import dedup_key, merge_companies, merge_pair
from core.opportunity_engine import evaluate_rules
from core.repository import (
    get_portfolio_by_company, list_active_rules, list_companies, list_company_signals,
    list_products, list_services, save_company, save_contact, save_opportunity,
)
from providers.base import ProviderError


@dataclass
class SyncResult:
    source_id: str
    companies_synced: int = 0
    contacts_synced: int = 0
    opportunities_generated: int = 0
    errors: list[str] = field(default_factory=list)


async def sync_source(
    session_factory: async_sessionmaker, source: SourceDescriptor, env: dict[str, str],
) -> SyncResult:
    """Busca empresas/contatos do provider da fonte, normaliza (dedup dentro
    da própria fonte) e reconcilia contra empresa já persistida de OUTRA
    fonte antes de salvar — nunca duplica empresa por aparecer em fontes
    diferentes (regra de domínio). Falha do provider vira SyncResult.errors —
    nunca exceção crua, nunca aborta as demais fontes de quem chama."""
    if source.build is None:
        return SyncResult(source_id=source.id, errors=["Esta fonte ainda não está disponível nesta versão."])

    try:
        provider = source.build(env)
        raw_companies = await provider.fetch_companies()
    except ProviderError as exc:
        return SyncResult(source_id=source.id, errors=[str(exc)])

    fetched = merge_companies(raw_companies)  # dedup dentro da própria fonte — ids seguem nativos do provider

    async with session_factory() as session:
        existing_by_key = {dedup_key(c): c for c in await list_companies(session)}

    # native_id (o que o provider reconhece, ex.: Salesforce Account Id) ->
    # Company final a persistir (id existente reconciliado, se já havia
    # empresa igual de outra fonte — senão o próprio id nativo).
    to_persist: dict[str, Company] = {}
    for company in fetched:
        match = existing_by_key.get(dedup_key(company))
        to_persist[company.id] = merge_pair(match, company) if match else company

    async with session_factory() as session:
        for final in to_persist.values():
            await save_company(session, final)

    errors: list[str] = []
    contacts_synced = 0
    async with session_factory() as session:
        for native_id, final in to_persist.items():
            try:
                contacts = await provider.fetch_contacts(native_id)
            except ProviderError as exc:
                errors.append(f"{final.name}: {exc}")
                continue
            for contact in contacts:
                if contact.company_id != final.id:
                    contact = contact.model_copy(update={"company_id": final.id})
                await save_contact(session, contact)
                contacts_synced += 1

    opportunities_generated = await _evaluate_rules_for_synced_companies(session_factory, to_persist.values())

    return SyncResult(
        source_id=source.id, companies_synced=len(to_persist),
        contacts_synced=contacts_synced, opportunities_generated=opportunities_generated, errors=errors,
    )


async def _evaluate_rules_for_synced_companies(
    session_factory: async_sessionmaker, companies: Iterable[Company],
) -> int:
    """Roda o motor de regras (Fase C) contra o portfólio já conhecido de
    cada empresa recém-sincronizada. Empresa sem Portfolio cadastrado é
    pulada — motor exige um Portfolio real, nunca inventa um vazio pra
    fingir avaliação."""
    async with session_factory() as session:
        rules = await list_active_rules(session)
        if not rules:
            return 0
        products = await list_products(session)
        services = await list_services(session)

    generated = 0
    async with session_factory() as session:
        for company in companies:
            portfolio = await get_portfolio_by_company(session, company.id)
            if portfolio is None:
                continue
            signals = await list_company_signals(session, company.id)
            opportunities = evaluate_rules(portfolio, rules, products=products, services=services, signals=signals)
            for opportunity in opportunities:
                await save_opportunity(session, opportunity)
                generated += 1

    return generated


async def sync_all_enabled_sources(
    session_factory: async_sessionmaker, env: dict[str, str],
) -> list[SyncResult]:
    """Sincroniza toda fonte implementada e habilitada (`{ENABLED_KEY}=true`
    no .env). Manual não entra aqui — não tem toggle (sempre disponível),
    e não há ainda cadastro manual persistente pra sincronizar."""
    results = []
    for source in SOURCES:
        if not source.implemented or source.enabled_key is None:
            continue
        if env.get(source.enabled_key) != "true":
            continue
        results.append(await sync_source(session_factory, source, env))
    return results
