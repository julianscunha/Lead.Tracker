"""
Rotas de dado real (Fase B.1/C do roadmap): sincronização + leitura de
companies/opportunities/métricas do banco (substituem sampleData.ts/
sampleMetrics.ts no frontend) + CRUD mínimo de regra de correlação e
catálogo (produto/serviço) pro editor de regras.
"""
from __future__ import annotations

import sys
from pathlib import Path

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import routes_settings  # _ENV_PATH acessado via módulo, não import direto — precisa
                                       # refletir monkeypatch de teste em routes_settings._ENV_PATH
from backend.db_session import session_factory
from backend.http_errors import raise_http
from backend.sync import sync_all_enabled_sources
from core.config import load_env
from core.dashboard_metrics import (
    compute_kpis, customer_vs_prospect, distribution_by_vendor,
    financial_potential_by_vendor, funnel_counts, opportunities_by_service,
)
from core.errors import DomainError, ErrorCategory
from core.models import Company, CorrelationRule, Product, RuleError, Service
from core.opportunity_engine import compute_severity_band
from core.repository import (
    list_companies, list_opportunities, list_products, list_rules, list_services,
    list_vendors, save_rule, update_opportunity_qualification,
)

router = APIRouter(tags=["lead_tracker-data"])


class SyncResultOut(BaseModel):
    source_id: str
    companies_synced: int
    contacts_synced: int
    opportunities_generated: int
    errors: list[str]


class OpportunityOut(BaseModel):
    id: str
    company_id: str
    company_name: str
    is_customer: bool
    type: str
    product_id: str | None
    product_name: str | None
    service_id: str | None
    service_name: str | None
    opportunity_score: float | None
    financial_potential: float | None
    strategic_score: float | None
    confidence_score: float | None
    evidence: list[str]
    justification: str | None
    sources: list[dict]
    status: str
    risk_flag: str | None
    scope_note: str | None
    criticality: str | None
    severity_note: str | None
    severity_band: str


class OpportunityQualificationIn(BaseModel):
    # Domínio (core/models.py) mantém os 3 campos como string aberta de propósito
    # (Fatia 5, "Design"). Aqui na fronteira HTTP, porém, qualquer cliente além da UI
    # (curl, integração futura) poderia gravar lixo que compute_severity_band
    # silenciosamente rebaixa a "não avaliado" — Literal fecha só esse ponto de entrada.
    scope_note: Literal["isolado", "parcial", "generalizado"] | None = None
    criticality: Literal["nao_critico", "critico_interno", "critico_exposto"] | None = None
    severity_note: str | None = None


class RuleIn(BaseModel):
    opportunity_type: str
    justification: str
    requires: list[str] = []
    absent: list[str] = []
    requires_category: list[str] = []
    absent_category: list[str] = []
    relation_type: str | None = None
    opportunity_score: float = 1.0
    confidence_score: float = 1.0
    active: bool = True


@router.post("/sync")
async def sync_now() -> list[SyncResultOut]:
    env = load_env(routes_settings._ENV_PATH)
    results = await sync_all_enabled_sources(session_factory, env)
    return [SyncResultOut(**vars(r)) for r in results]


@router.get("/companies")
async def get_companies() -> list[Company]:
    async with session_factory() as session:
        return await list_companies(session)


def _to_opportunity_out(
    o, companies: dict[str, Company], products: dict[str, str], services: dict[str, str],
) -> OpportunityOut:
    company = companies.get(o.company_id)
    return OpportunityOut(
        id=o.id, company_id=o.company_id,
        company_name=company.name if company else "(empresa removida)",
        is_customer=company.is_customer if company else False,
        type=o.type, product_id=o.product_id, product_name=products.get(o.product_id),
        service_id=o.service_id, service_name=services.get(o.service_id),
        opportunity_score=o.opportunity_score, financial_potential=o.financial_potential,
        strategic_score=o.strategic_score, confidence_score=o.confidence_score,
        evidence=o.evidence, justification=o.justification,
        sources=[s.model_dump() for s in o.sources], status=o.status.value,
        risk_flag=o.risk_flag, scope_note=o.scope_note, criticality=o.criticality,
        severity_note=o.severity_note,
        severity_band=compute_severity_band(o.scope_note, o.criticality),
    )


@router.get("/opportunities")
async def get_opportunities(company_id: str | None = None) -> list[OpportunityOut]:
    async with session_factory() as session:
        opportunities = await list_opportunities(session, company_id=company_id)
        companies = {c.id: c for c in await list_companies(session)}
        products = {p.id: p.name for p in await list_products(session)}
        services = {s.id: s.name for s in await list_services(session)}

    return [_to_opportunity_out(o, companies, products, services) for o in opportunities]


@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity_qualification_route(opportunity_id: str, body: OpportunityQualificationIn) -> OpportunityOut:
    async with session_factory() as session:
        updated = await update_opportunity_qualification(
            session, opportunity_id, body.scope_note, body.criticality, body.severity_note,
        )
        if updated is None:
            raise_http(DomainError(ErrorCategory.NOT_FOUND, "Oportunidade não encontrada."))
        companies = {c.id: c for c in await list_companies(session)}
        products = {p.id: p.name for p in await list_products(session)}
        services = {s.id: s.name for s in await list_services(session)}

    return _to_opportunity_out(updated, companies, products, services)


@router.get("/products")
async def get_products() -> list[Product]:
    async with session_factory() as session:
        return await list_products(session)


@router.get("/services")
async def get_services() -> list[Service]:
    async with session_factory() as session:
        return await list_services(session)


@router.get("/rules")
async def get_rules() -> list[CorrelationRule]:
    async with session_factory() as session:
        return await list_rules(session)


@router.post("/rules")
async def create_rule(body: RuleIn) -> CorrelationRule:
    try:
        rule = CorrelationRule(**body.model_dump())
    except RuleError as exc:
        raise_http(DomainError(ErrorCategory.INVALID_DATA, str(exc)))
    async with session_factory() as session:
        await save_rule(session, rule)
    return rule


@router.get("/dashboard-metrics")
async def get_dashboard_metrics() -> dict:
    async with session_factory() as session:
        companies = await list_companies(session)
        opportunities = await list_opportunities(session)
        vendors = await list_vendors(session)
        services = await list_services(session)

    vendor_names = {v.id: v.name for v in vendors}
    service_names = {s.id: s.name for s in services}
    kpis = compute_kpis(companies, opportunities, vendor_names, service_names)

    return {
        "kpis": {
            "opportunities_identified": kpis.opportunities_identified,
            "customers_analyzed": kpis.customers_analyzed,
            "prospects_analyzed": kpis.prospects_analyzed,
            "financial_potential_total": kpis.financial_potential_total,
            "product_opportunities": kpis.product_opportunities,
            "service_opportunities": kpis.service_opportunities,
            "top_vendor": kpis.top_vendor,
            "top_service": kpis.top_service,
        },
        "vendor_distribution": distribution_by_vendor(opportunities, vendor_names),
        "financial_by_vendor": financial_potential_by_vendor(opportunities, vendor_names),
        "opportunities_by_service": opportunities_by_service(opportunities, service_names),
        "customer_vs_prospect": customer_vs_prospect(companies),
        "funnel_counts": funnel_counts(opportunities),
    }
