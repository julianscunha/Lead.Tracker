"""
Rotas de dado real (Fase B.1/C do roadmap): sincronização + leitura de
companies/opportunities/métricas do banco (substituem sampleData.ts/
sampleMetrics.ts no frontend) + CRUD mínimo de regra de correlação e
catálogo (produto/serviço) pro editor de regras.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import routes_settings  # _ENV_PATH acessado via módulo, não import direto — precisa
                                       # refletir monkeypatch de teste em routes_settings._ENV_PATH
from backend.db_session import session_factory
from backend.http_errors import raise_http
from backend.sync import sync_all_enabled_sources
from core.config import load_env
from core.dashboard_metrics import (
    compute_kpis, compute_rep_coverage, compute_weighted_potential, count_aging_opportunities,
    count_zombie_opportunities, customer_vs_prospect, distribution_by_vendor, exclude_zombies,
    financial_potential_by_vendor, funnel_counts, funnel_reach, opportunities_by_service, potential_by_rep,
    potential_by_segment, potential_by_source,
)
from core.errors import DomainError, ErrorCategory
from core.models import (
    Company, CorrelationRule, DismissalReason, DismissalReasonRequiredError, ICPProfile, Opportunity,
    OpportunityStatus, PeriodType, Product, RepTarget, RuleError, Service,
    StatusChangeRequiresJustificationError,
)
from core.geo_discovery import build_discovery_records
from core.geo_promotion import parse_promotion_daily_cap, parse_promotion_min_score, select_promotions
from core.geo_scoring import category_matches, score_place_signal
from core.icp import derive_icp_suggestion
from core.opportunity_engine import (
    compute_account_health, compute_qbr_suggested_days, compute_severity_band, current_period_key,
    is_aging_opportunity, parse_aging_sla_days, rep_target_id,
)
from core.repository import (
    count_geo_discoveries_today, get_icp_profile, list_companies, list_company_signals,
    list_latest_snapshot, list_opportunities, list_products, list_rep_targets, list_rules, list_services,
    list_vendors, save_company, save_icp_profile, save_opportunity, save_rep_target, save_rule,
    update_company_renewal_date, update_opportunity_qualification, update_opportunity_status,
)
from providers.base import ProviderError
from providers.google_maps import GoogleMapsProvider, PlaceSignal

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
    renewal_date: datetime | None
    account_health: str
    qbr_suggested_days: int
    qbr_reason: str
    is_aging: bool
    dismissal_reason: str | None


class OpportunityQualificationIn(BaseModel):
    # Domínio (core/models.py) mantém os 3 campos como string aberta de propósito
    # (Fatia 5, "Design"). Aqui na fronteira HTTP, porém, qualquer cliente além da UI
    # (curl, integração futura) poderia gravar lixo que compute_severity_band
    # silenciosamente rebaixa a "não avaliado" — Literal fecha só esse ponto de entrada.
    scope_note: Literal["isolado", "parcial", "generalizado"] | None = None
    criticality: Literal["nao_critico", "critico_interno", "critico_exposto"] | None = None
    severity_note: str | None = None


class CompanyRenewalDateIn(BaseModel):
    renewal_date: datetime | None = None


class OpportunityStatusIn(BaseModel):
    new_status: Literal["detected", "qualified", "reviewed", "contacted", "opportunity", "dismissed"]
    note: str | None = None
    dismissal_reason: Literal["no_evidence", "not_fit", "not_qualified", "false_positive", "other"] | None = None


_PERIOD_KEY_PATTERN = {"monthly": re.compile(r"^\d{4}-\d{2}$"), "quarterly": re.compile(r"^\d{4}-Q[1-4]$")}


class RepTargetIn(BaseModel):
    rep_id: str = Field(min_length=1)
    period_type: Literal["monthly", "quarterly"]
    period_key: str
    target_amount: float = Field(ge=0)

    @field_validator("period_key")
    @classmethod
    def _period_key_matches_period_type(cls, value: str, info) -> str:
        # Achado da revisão de código: period_key é texto livre do cliente
        # (GET /dashboard-metrics sempre calcula "hoje" via
        # current_period_key, mas o cadastro manual não passava por essa
        # função) — um typo aqui nunca junta com nenhum período real,
        # degradando pra "sem meta definida" sem nenhum aviso pro usuário,
        # exatamente o sintoma que o roadmap pediu pra nunca acontecer
        # silenciosamente. Validado contra o mesmo formato que
        # `current_period_key` produz, nunca aceito solto.
        period_type = info.data.get("period_type")
        pattern = _PERIOD_KEY_PATTERN.get(period_type)
        if pattern and not pattern.match(value):
            expected = "AAAA-MM" if period_type == "monthly" else "AAAA-Q1..4"
            raise ValueError(f"period_key precisa seguir o formato {expected} (ex.: 2026-09 / 2026-Q3)")
        return value


class RepTargetOut(BaseModel):
    rep_id: str
    period_type: str
    period_key: str
    target_amount: float


class ICPProfileIn(BaseModel):
    reference_product_id: str | None = None
    place_category: str | None = None
    company_size_hint: str | None = None
    radius_km: float | None = Field(default=None, ge=0)
    search_origin_address: str | None = None


class ICPProfileOut(BaseModel):
    reference_product_id: str | None
    place_category: str | None
    company_size_hint: str | None
    radius_km: float | None
    search_origin_address: str | None


class ICPSuggestionOut(BaseModel):
    industry_hint: str | None
    industry_hint_share: float | None
    company_size_hint: str | None
    company_size_hint_share: float | None
    sample_size: int
    confidence: str


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


async def _account_health_map(
    session, opportunities: list[Opportunity], companies: dict[str, Company],
) -> dict[str, tuple[str, int, str]]:
    """Saúde/cadência de QBR é por conta, não por oportunidade — calculada
    uma vez por empresa presente na lista e reaproveitada em toda linha
    daquela empresa (mesmo padrão de company_name/is_customer, que já se
    repetem hoje). "Aberta" pra fins de confidence médio = qualquer status
    != dismissed (dismissed é a única baixa explícita do fluxo)."""
    now = datetime.now(timezone.utc)
    by_company: dict[str, list[Opportunity]] = {}
    for o in opportunities:
        by_company.setdefault(o.company_id, []).append(o)

    result: dict[str, tuple[str, int, str]] = {}
    for company_id, opps in by_company.items():
        company = companies.get(company_id)
        open_confidences = [
            o.confidence_score for o in opps
            if o.status != OpportunityStatus.DISMISSED and o.confidence_score is not None
        ]
        avg_open_confidence = sum(open_confidences) / len(open_confidences) if open_confidences else None

        recency_days: int | None = None
        renewal_days: int | None = None
        if company is not None:
            if company.last_activity_at is not None:
                last_activity_at = company.last_activity_at
                if last_activity_at.tzinfo is None:
                    last_activity_at = last_activity_at.replace(tzinfo=timezone.utc)
                recency_days = (now - last_activity_at).days
            if company.renewal_date is not None:
                renewal_date = company.renewal_date
                if renewal_date.tzinfo is None:
                    renewal_date = renewal_date.replace(tzinfo=timezone.utc)
                renewal_days = (renewal_date - now).days

        signals = await list_company_signals(session, company_id)
        open_signal_count = sum(1 for s in signals if s.status == "open")

        health = compute_account_health(recency_days, avg_open_confidence)
        days, reason = compute_qbr_suggested_days(health, renewal_days, open_signal_count)
        result[company_id] = (health, days, reason)
    return result


def _to_opportunity_out(
    o, companies: dict[str, Company], products: dict[str, str], services: dict[str, str],
    health_map: dict[str, tuple[str, int, str]], aging_sla_days: int,
) -> OpportunityOut:
    company = companies.get(o.company_id)
    # health_map é sempre construído a partir da mesma lista de oportunidades
    # que esta função itera — o fallback abaixo é inalcançável hoje; existe
    # só como rede de segurança caso um chamador futuro passe listas
    # desalinhadas, nunca deve mascarar um bug de wiring silenciosamente.
    health, qbr_days, qbr_reason = health_map.get(o.company_id, ("dados_insuficientes", 90, "revisao_de_rotina"))
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
        renewal_date=company.renewal_date if company else None,
        account_health=health, qbr_suggested_days=qbr_days, qbr_reason=qbr_reason,
        is_aging=is_aging_opportunity(o.status.value, o.first_detected_at, datetime.now(timezone.utc), aging_sla_days),
        dismissal_reason=o.dismissal_reason.value if o.dismissal_reason else None,
    )


@router.get("/opportunities")
async def get_opportunities(company_id: str | None = None) -> list[OpportunityOut]:
    aging_sla_days = parse_aging_sla_days(load_env(routes_settings._ENV_PATH))
    async with session_factory() as session:
        opportunities = await list_opportunities(session, company_id=company_id)
        companies = {c.id: c for c in await list_companies(session)}
        products = {p.id: p.name for p in await list_products(session)}
        services = {s.id: s.name for s in await list_services(session)}
        health_map = await _account_health_map(session, opportunities, companies)

    return [_to_opportunity_out(o, companies, products, services, health_map, aging_sla_days) for o in opportunities]


@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity_qualification_route(opportunity_id: str, body: OpportunityQualificationIn) -> OpportunityOut:
    aging_sla_days = parse_aging_sla_days(load_env(routes_settings._ENV_PATH))
    async with session_factory() as session:
        updated = await update_opportunity_qualification(
            session, opportunity_id, body.scope_note, body.criticality, body.severity_note,
        )
        if updated is None:
            raise_http(DomainError(ErrorCategory.NOT_FOUND, "Oportunidade não encontrada."))
        companies = {c.id: c for c in await list_companies(session)}
        products = {p.id: p.name for p in await list_products(session)}
        services = {s.id: s.name for s in await list_services(session)}
        health_map = await _account_health_map(session, [updated], companies)

    return _to_opportunity_out(updated, companies, products, services, health_map, aging_sla_days)


@router.patch("/opportunities/{opportunity_id}/status")
async def update_opportunity_status_route(opportunity_id: str, body: OpportunityStatusIn) -> OpportunityOut:
    aging_sla_days = parse_aging_sla_days(load_env(routes_settings._ENV_PATH))
    async with session_factory() as session:
        dismissal_reason = DismissalReason(body.dismissal_reason) if body.dismissal_reason else None
        try:
            updated = await update_opportunity_status(
                session, opportunity_id, OpportunityStatus(body.new_status), body.note, dismissal_reason,
            )
        except StatusChangeRequiresJustificationError:
            raise_http(DomainError(
                ErrorCategory.INVALID_DATA,
                "Pular vários estágios de uma vez ou reabrir uma oportunidade descartada exige uma justificativa.",
            ))
        except DismissalReasonRequiredError:
            raise_http(DomainError(
                ErrorCategory.INVALID_DATA,
                "Descartar uma oportunidade exige selecionar um motivo categorizado.",
            ))
        if updated is None:
            raise_http(DomainError(ErrorCategory.NOT_FOUND, "Oportunidade não encontrada."))
        companies = {c.id: c for c in await list_companies(session)}
        products = {p.id: p.name for p in await list_products(session)}
        services = {s.id: s.name for s in await list_services(session)}
        health_map = await _account_health_map(session, [updated], companies)

    return _to_opportunity_out(updated, companies, products, services, health_map, aging_sla_days)


@router.patch("/companies/{company_id}/renewal-date")
async def update_company_renewal_date_route(company_id: str, body: CompanyRenewalDateIn) -> Company:
    async with session_factory() as session:
        updated = await update_company_renewal_date(session, company_id, body.renewal_date)
        if updated is None:
            raise_http(DomainError(ErrorCategory.NOT_FOUND, "Empresa não encontrada."))
    return updated


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


@router.post("/rep-targets")
async def create_rep_target(body: RepTargetIn) -> RepTargetOut:
    period_type = PeriodType(body.period_type)
    target = RepTarget(
        id=rep_target_id(body.rep_id, period_type, body.period_key), rep_id=body.rep_id,
        period_type=period_type, period_key=body.period_key, target_amount=body.target_amount,
    )
    async with session_factory() as session:
        await save_rep_target(session, target)
    return RepTargetOut(
        rep_id=target.rep_id, period_type=target.period_type.value,
        period_key=target.period_key, target_amount=target.target_amount,
    )


@router.get("/rep-targets")
async def get_rep_targets(period_type: Literal["monthly", "quarterly"] = "monthly", period_key: str | None = None) -> list[RepTargetOut]:
    resolved_period_type = PeriodType(period_type)
    resolved_period_key = period_key or current_period_key(resolved_period_type, date.today())
    async with session_factory() as session:
        targets = await list_rep_targets(session, resolved_period_type, resolved_period_key)
    return [
        RepTargetOut(rep_id=t.rep_id, period_type=t.period_type.value, period_key=t.period_key, target_amount=t.target_amount)
        for t in targets
    ]


@router.get("/icp-profile")
async def get_icp_profile_route() -> ICPProfileOut:
    async with session_factory() as session:
        profile = await get_icp_profile(session)
    if profile is None:
        # Sem configuração ainda — corpo vazio (todo mundo None) é o
        # estado esperado antes do primeiro save, nunca 404: é um
        # singleton de configuração, não um recurso que "não existe".
        return ICPProfileOut(
            reference_product_id=None, place_category=None, company_size_hint=None, radius_km=None,
            search_origin_address=None,
        )
    return ICPProfileOut(
        reference_product_id=profile.reference_product_id, place_category=profile.place_category,
        company_size_hint=profile.company_size_hint, radius_km=profile.radius_km,
        search_origin_address=profile.search_origin_address,
    )


@router.put("/icp-profile")
async def update_icp_profile_route(body: ICPProfileIn) -> ICPProfileOut:
    profile = ICPProfile(
        reference_product_id=body.reference_product_id, place_category=body.place_category,
        company_size_hint=body.company_size_hint, radius_km=body.radius_km,
        search_origin_address=body.search_origin_address,
    )
    async with session_factory() as session:
        await save_icp_profile(session, profile)
    return ICPProfileOut(
        reference_product_id=profile.reference_product_id, place_category=profile.place_category,
        company_size_hint=profile.company_size_hint, radius_km=profile.radius_km,
        search_origin_address=profile.search_origin_address,
    )


@router.get("/icp-suggestion")
async def get_icp_suggestion_route() -> ICPSuggestionOut | None:
    """200 com corpo JSON `null` (nunca 404/204) quando não há nenhum
    cliente satisfeito ainda — nunca inventa sugestão sem dado nenhum
    pra sustentá-la. Nunca auto-aplica no `ICPProfile`: só calcula e
    devolve, o usuário revisa no wizard (módulo 6) antes de qualquer
    uso real."""
    async with session_factory() as session:
        companies = await list_companies(session)
        opportunities = await list_opportunities(session)
    suggestion = derive_icp_suggestion(companies, opportunities)
    if suggestion is None:
        return None
    return ICPSuggestionOut(
        industry_hint=suggestion.industry_hint, industry_hint_share=suggestion.industry_hint_share,
        company_size_hint=suggestion.company_size_hint, company_size_hint_share=suggestion.company_size_hint_share,
        sample_size=suggestion.sample_size, confidence=suggestion.confidence,
    )


class GeoDiscoveryRequest(BaseModel):
    rep_id: str = Field(min_length=1)
    reference_product_id: str | None = None
    search_origin_address: str = Field(min_length=1)
    radius_km: float = Field(gt=0)
    place_category: str | None = None
    company_size_hint: str | None = None


class GeoDiscoveryItemOut(BaseModel):
    """Fase E, módulo 7 (`geo-results-view`) — card de resultado, campos
    escolhidos em consulta ao agente Sales Engineer pra um vendedor
    decidir rapidamente quem contatar primeiro sem pedir ajuda técnica:
    nome, categoria (e se bateu com o critério), avaliação/reviews
    (proxy de porte), endereço, score visual. Decisão explícita do
    Sales Engineer: LISTA visual, nunca mapa embutido nesta fatia (exigiria
    capturar lat/lng — mudança de schema — e mais uma integração/superfície
    de erro, sem ganho real de decisão sobre uma lista bem desenhada)."""
    place_id: str
    name: str
    category: str | None
    category_matches: bool
    rating: float | None
    review_count: int
    formatted_address: str | None
    score: float | None
    company_id: str | None = None
    opportunity_id: str | None = None


class GeoDiscoveryResultOut(BaseModel):
    promoted: list[GeoDiscoveryItemOut]
    deferred: list[GeoDiscoveryItemOut]
    rejected: list[GeoDiscoveryItemOut]


@router.post("/geo-discovery/run")
async def run_geo_discovery(body: GeoDiscoveryRequest) -> GeoDiscoveryResultOut:
    """Orquestra a esteira completa (Fase E, módulo 6, `icp-wizard-ui`):
    `discover()` (módulo 2) → `score_place_signal` (módulo 4) →
    `select_promotions` (módulo 5) → persiste só quem foi promovido.
    Nunca bloqueia por cota esgotada (achado do módulo 5) — sempre roda
    a busca inteira, classifica tudo, e devolve as 3 listas completas
    (módulo 7) pro wizard mostrar em linguagem comercial ("prontos para
    contato" / "na fila para amanhã" / "fora do critério").

    ponytail: contagem e escrita da cota diária não são atômicas — duas
    requisições concorrentes pro MESMO rep podem cada uma ler "0
    promovidas hoje" e promover até o cap inteiro cada, estourando a
    cota combinada. Aceitável pra esta fatia (ferramenta de uso manual,
    um rep clicando "Buscar agora" por vez) — upgrade se concorrência
    real aparecer: lock consultivo por rep, ou constraint de unicidade
    que force serialização no banco."""
    env = load_env(routes_settings._ENV_PATH)
    try:
        # Construção de GoogleMapsProvider também levanta ProviderError
        # (chave ausente) — de propósito dentro do mesmo try do discover().
        provider = GoogleMapsProvider(env.get("GOOGLE_MAPS_API_KEY", ""))
        signals = await provider.discover(body.search_origin_address, body.radius_km, body.place_category)
    except ProviderError as exc:
        raise_http(exc)

    scored = [(signal, score_place_signal(signal, body.place_category)) for signal in signals]
    min_score = parse_promotion_min_score(env)
    daily_cap = parse_promotion_daily_cap(env)

    async with session_factory() as session:
        # Achado da revisão de código: date.today() é a data LOCAL do
        # servidor, mas Company.created_at é sempre gravado em UTC
        # (core/models.py::_now) — comparar os dois desalinha a cota
        # perto da meia-noite em qualquer servidor fora de UTC. A cota
        # diária (garantia central do módulo 5) precisa da mesma
        # referência de fuso nos dois lados.
        already_promoted_today = await count_geo_discoveries_today(
            session, body.rep_id, datetime.now(timezone.utc).date(),
        )
        decision = select_promotions(scored, min_score, daily_cap, already_promoted_today)

        score_by_place_id = {signal.place_id: score for signal, score in scored if score is not None}

        def _item(signal: PlaceSignal, company_id: str | None = None, opportunity_id: str | None = None) -> GeoDiscoveryItemOut:
            return GeoDiscoveryItemOut(
                place_id=signal.place_id, name=signal.name, category=signal.category,
                category_matches=category_matches(signal.category, body.place_category),
                rating=signal.rating, review_count=signal.review_count,
                formatted_address=signal.formatted_address, score=score_by_place_id.get(signal.place_id),
                company_id=company_id, opportunity_id=opportunity_id,
            )

        promoted_out: list[GeoDiscoveryItemOut] = []
        for signal in decision.promoted:
            score = score_by_place_id[signal.place_id]
            company, opportunity = build_discovery_records(
                signal, score, body.rep_id, body.company_size_hint, body.reference_product_id,
            )
            await save_company(session, company)
            await save_opportunity(session, opportunity)
            promoted_out.append(_item(signal, company_id=company.id, opportunity_id=opportunity.id))

        deferred_out = [_item(signal) for signal in decision.deferred]
        rejected_out = [_item(signal) for signal in decision.rejected]

    # Ordenação padrão por score desc dentro de cada grupo (Sales Engineer) —
    # score None (descarte por business_status) sempre por último, nunca
    # confundido com score 0.0 real.
    def _sort_key(item: GeoDiscoveryItemOut) -> float:
        return item.score if item.score is not None else -1.0

    promoted_out.sort(key=_sort_key, reverse=True)
    deferred_out.sort(key=_sort_key, reverse=True)
    rejected_out.sort(key=_sort_key, reverse=True)

    return GeoDiscoveryResultOut(promoted=promoted_out, deferred=deferred_out, rejected=rejected_out)


@router.get("/dashboard-metrics")
async def get_dashboard_metrics(period_type: Literal["monthly", "quarterly"] = "monthly") -> dict:
    aging_sla_days = parse_aging_sla_days(load_env(routes_settings._ENV_PATH))
    resolved_period_type = PeriodType(period_type)
    resolved_period_key = current_period_key(resolved_period_type, date.today())
    async with session_factory() as session:
        companies = await list_companies(session)
        opportunities = await list_opportunities(session)
        rep_targets = await list_rep_targets(session, resolved_period_type, resolved_period_key)
        vendors = await list_vendors(session)
        services = await list_services(session)
        snapshot = await list_latest_snapshot(session)

    vendor_names = {v.id: v.name for v in vendors}
    service_names = {s.id: s.name for s in services}
    kpis = compute_kpis(companies, opportunities, vendor_names, service_names)

    # Fase D — tudo abaixo lê do snapshot diário, nunca das listas ao vivo
    # acima (decisão de arquitetura do roadmap). Zumbi nunca entra em
    # métrica de "pipeline saudável" (blindagem obrigatória) — filtrado
    # antes do potencial ponderado/cortes, mas contado à parte pra UI
    # mostrar o número, não escondê-lo.
    healthy_snapshot = exclude_zombies(snapshot)
    weighted = compute_weighted_potential(healthy_snapshot)

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
        "funnel_reach": [
            {"stage": r.stage, "reach_count": r.reach_count, "reach_ratio_from_previous": r.reach_ratio_from_previous}
            for r in funnel_reach(snapshot)
        ],
        "weighted_potential": {
            "gross_total": weighted.gross_total,
            "weighted_evaluated_total": weighted.weighted_evaluated_total,
            "weighted_estimated_total": weighted.weighted_estimated_total,
        },
        "potential_by_rep": potential_by_rep(healthy_snapshot),
        "potential_by_segment": potential_by_segment(healthy_snapshot),
        "potential_by_source": potential_by_source(healthy_snapshot),
        "zombie_count": count_zombie_opportunities(snapshot),
        "aging_count": count_aging_opportunities(snapshot, aging_sla_days, datetime.now(timezone.utc)),
        "aging_sla_days": aging_sla_days,
        "rep_coverage": [
            {"rep_id": c.rep_id, "actual": c.actual, "target": c.target, "coverage_ratio": c.coverage_ratio}
            for c in compute_rep_coverage(potential_by_rep(healthy_snapshot), {t.rep_id: t.target_amount for t in rep_targets})
        ],
        "coverage_period_type": resolved_period_type.value,
        "coverage_period_key": resolved_period_key,
    }
