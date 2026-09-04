"""
Rotas de dado real (Fase B.1 do roadmap): sincronização + leitura de
companies/opportunities/métricas do banco — substituem sampleData.ts/
sampleMetrics.ts no frontend. Nenhuma rota aqui gera oportunidade por
regra (sem persistência de regra ainda — ver docs/specs/fase-b1-ligacao-real.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import routes_settings  # _ENV_PATH acessado via módulo, não import direto — precisa
                                       # refletir monkeypatch de teste em routes_settings._ENV_PATH
from backend.db_session import session_factory
from backend.sync import sync_all_enabled_sources
from core.config import load_env
from core.dashboard_metrics import (
    compute_kpis, customer_vs_prospect, distribution_by_vendor,
    financial_potential_by_vendor, funnel_counts, opportunities_by_service,
)
from core.models import Company
from core.repository import list_companies, list_opportunities, list_products, list_services, list_vendors

router = APIRouter(tags=["lead_tracker-data"])


class SyncResultOut(BaseModel):
    source_id: str
    companies_synced: int
    contacts_synced: int
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


@router.post("/sync")
async def sync_now() -> list[SyncResultOut]:
    env = load_env(routes_settings._ENV_PATH)
    results = await sync_all_enabled_sources(session_factory, env)
    return [SyncResultOut(**vars(r)) for r in results]


@router.get("/companies")
async def get_companies() -> list[Company]:
    async with session_factory() as session:
        return await list_companies(session)


@router.get("/opportunities")
async def get_opportunities(company_id: str | None = None) -> list[OpportunityOut]:
    async with session_factory() as session:
        opportunities = await list_opportunities(session, company_id=company_id)
        companies = {c.id: c for c in await list_companies(session)}
        products = {p.id: p.name for p in await list_products(session)}
        services = {s.id: s.name for s in await list_services(session)}

    out: list[OpportunityOut] = []
    for o in opportunities:
        company = companies.get(o.company_id)
        out.append(OpportunityOut(
            id=o.id, company_id=o.company_id,
            company_name=company.name if company else "(empresa removida)",
            is_customer=company.is_customer if company else False,
            type=o.type, product_id=o.product_id, product_name=products.get(o.product_id),
            service_id=o.service_id, service_name=services.get(o.service_id),
            opportunity_score=o.opportunity_score, financial_potential=o.financial_potential,
            strategic_score=o.strategic_score, confidence_score=o.confidence_score,
            evidence=o.evidence, justification=o.justification,
            sources=[s.model_dump() for s in o.sources], status=o.status.value,
        ))
    return out


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
