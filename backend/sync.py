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
from core.field_mapping import split_custom_fields
from core.models import Company
from core.normalization import dedup_key, merge_companies, merge_pair
from core.opportunity_engine import evaluate_rules
from core.repository import (
    apply_field_mapping_updates, get_portfolio_by_company, list_active_rules, list_companies,
    list_company_signals, list_field_mappings, list_products, list_services, recompute_daily_snapshot,
    save_company, save_contact, save_opportunity,
)
from providers.base import DataProvider, ProviderError


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

    errors.extend(await _apply_field_mappings_for_synced_companies(session_factory, provider, source.id, to_persist))

    opportunities_generated = await _evaluate_rules_for_synced_companies(session_factory, to_persist.values())

    return SyncResult(
        source_id=source.id, companies_synced=len(to_persist),
        contacts_synced=contacts_synced, opportunities_generated=opportunities_generated, errors=errors,
    )


async def _apply_field_mappings_for_synced_companies(
    session_factory: async_sessionmaker, provider: DataProvider, provider_id: str, to_persist: dict[str, Company],
) -> list[str]:
    """Fase F, módulo 4 (`mapping-driven-context-split`). Só chama
    `fetch_context()` (uma requisição por empresa) quando existe pelo menos
    um `FieldMapping` configurado pra esta fonte — instalação sem nenhum
    mapeamento (o caso comum hoje) não paga o custo extra de rede, e o
    comportamento de sync sem Fase F configurada fica idêntico ao de antes
    deste módulo. Falha de `fetch_context` numa empresa vira erro
    reportado, nunca aborta as demais (mesmo padrão do loop de contatos).

    Achado da revisão de código: além de escrever no banco, atualiza
    `to_persist[native_id]` em memória (o dict é mutado in-place, o mesmo
    objeto que `sync_source` passa adiante) — sem isso, o motor de regras
    (`_evaluate_rules_for_synced_companies`, chamado logo depois com esses
    mesmos objetos) avaliaria contra `industry`/`deal_size_hint` ainda
    `None` na primeira sincronização com um mapeamento novo, e só refletiria
    o valor mapeado no próximo `/sync` — quieto hoje (nenhuma regra lê esses
    campos ainda), mas vira bug real no dia em que uma regra passar a usar
    `deal_size_hint`, exatamente o motivo do campo existir."""
    async with session_factory() as session:
        mappings = await list_field_mappings(session, provider_id)
    if not mappings:
        return []

    errors: list[str] = []
    async with session_factory() as session:
        for native_id, final in list(to_persist.items()):
            try:
                context = await provider.fetch_context(native_id)
            except ProviderError as exc:
                errors.append(f"{final.name}: {exc}")
                continue
            custom_fields = context.extra.get("custom_fields", {})
            if not custom_fields:
                continue
            updates, _remaining = split_custom_fields(custom_fields, mappings)
            if not updates:
                continue
            await apply_field_mapping_updates(session, final.id, updates)
            to_persist[native_id] = final.model_copy(update=updates)

    return errors


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
            opportunities = evaluate_rules(
                portfolio, rules, products=products, services=services, signals=signals, company=company,
            )
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

    # Fase D — snapshot diário recalculado no fim de TODO /sync (mesmo sem
    # nenhuma fonte habilitada rodar de fato), nunca em tempo real na leitura
    # do dashboard. Reflete o estado de todas as oportunidades já
    # persistidas, não só as tocadas nesta rodada.
    async with session_factory() as session:
        await recompute_daily_snapshot(session)

    return results
