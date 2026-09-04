"""
Repositório — ponte entre os modelos de domínio (Pydantic,
core/models.py) e as tabelas (SQLAlchemy, core/db_models.py).

Upsert via session.merge() (insere ou atualiza pela PK, sem exists-check
manual). Mapeamento Pydantic<->ORM fica explícito por entidade — 9 entidades
com forma idêntica de CRUD justificam esse tanto de repetição; um
Repository[T] genérico esconderia a diferença de campos entre elas.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_models import (
    CompanyORM, CompanySignalORM, ContactORM, CorrelationRuleORM, OpportunityORM,
    OpportunityStatusChangeORM, PortfolioORM, ProductORM, ServiceORM, VendorORM,
)
from core.models import (
    Company, CompanySignal, ContextNote, Contact, CorrelationRule, Opportunity, OpportunityStatus,
    OpportunityStatusChange, Portfolio, Product, ProductRelation, Service, SourceRef, Vendor,
)


def _sources_to_json(sources: list[SourceRef]) -> list[dict]:
    return [s.model_dump() for s in sources]


def _sources_from_json(data: list[dict] | None) -> list[SourceRef]:
    return [SourceRef(**d) for d in (data or [])]


def _note_to_json(note: ContextNote | None) -> dict | None:
    return note.model_dump(mode="json") if note else None


def _note_from_json(data: dict | None) -> ContextNote | None:
    return ContextNote(**data) if data else None


def _notes_to_json(notes: list[ContextNote]) -> list[dict]:
    return [n.model_dump(mode="json") for n in notes]


def _notes_from_json(data: list[dict] | None) -> list[ContextNote]:
    return [ContextNote(**d) for d in (data or [])]


def _relations_to_json(relations: list[ProductRelation]) -> list[dict]:
    return [r.model_dump() for r in relations]


def _relations_from_json(data: list[dict] | None) -> list[ProductRelation]:
    return [ProductRelation(**d) for d in (data or [])]


def _ensure_utc(value: datetime) -> datetime:
    """SQLite/SQLAlchemy descarta tzinfo ao ler de volta — sempre gravamos em
    UTC (core/models.py _now()), então reanexa aqui em vez de deixar o
    chamador comparar aware com naive silenciosamente."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def _upsert(session: AsyncSession, row) -> None:
    await session.merge(row)
    await session.commit()


# ── Vendor ───────────────────────────────────────────────────────────────────

async def save_vendor(session: AsyncSession, vendor: Vendor) -> None:
    await _upsert(session, VendorORM(id=vendor.id, name=vendor.name))


async def list_vendors(session: AsyncSession) -> list[Vendor]:
    rows = (await session.execute(select(VendorORM))).scalars().all()
    return [Vendor(id=r.id, name=r.name) for r in rows]


# ── Product ──────────────────────────────────────────────────────────────────

async def save_product(session: AsyncSession, product: Product) -> None:
    await _upsert(session, ProductORM(
        id=product.id, vendor_id=product.vendor_id, name=product.name,
        aliases=product.aliases, description=product.description,
        status=product.status, category=product.category,
        related_services=_relations_to_json(product.related_services),
    ))


async def list_products(session: AsyncSession) -> list[Product]:
    rows = (await session.execute(select(ProductORM))).scalars().all()
    return [Product(
        id=r.id, vendor_id=r.vendor_id, name=r.name, aliases=r.aliases,
        description=r.description, status=r.status, category=r.category,
        related_services=_relations_from_json(r.related_services),
    ) for r in rows]


# ── Service ──────────────────────────────────────────────────────────────────

async def save_service(session: AsyncSession, service: Service) -> None:
    await _upsert(session, ServiceORM(
        id=service.id, name=service.name, description=service.description,
        status=service.status, category=service.category,
    ))


async def list_services(session: AsyncSession) -> list[Service]:
    rows = (await session.execute(select(ServiceORM))).scalars().all()
    return [Service(
        id=r.id, name=r.name, description=r.description, status=r.status, category=r.category,
    ) for r in rows]


# ── Company ──────────────────────────────────────────────────────────────────

def _company_from_row(row: CompanyORM) -> Company:
    return Company(
        id=row.id, name=row.name, legal_name=row.legal_name, website=row.website,
        is_customer=row.is_customer, customer_status=row.customer_status,
        sources=_sources_from_json(row.sources), created_at=_ensure_utc(row.created_at), updated_at=_ensure_utc(row.updated_at),
        rep_id=row.rep_id, segment=row.segment, region=row.region,
        trigger_event=_note_from_json(row.trigger_event),
        attempted_solutions=_notes_from_json(row.attempted_solutions),
        strategic_context=_note_from_json(row.strategic_context),
        last_activity_at=_ensure_utc(row.last_activity_at) if row.last_activity_at else None,
    )


async def save_company(session: AsyncSession, company: Company) -> None:
    await _upsert(session, CompanyORM(
        id=company.id, name=company.name, legal_name=company.legal_name, website=company.website,
        is_customer=company.is_customer, customer_status=company.customer_status,
        sources=_sources_to_json(company.sources), created_at=company.created_at, updated_at=company.updated_at,
        rep_id=company.rep_id, segment=company.segment, region=company.region,
        trigger_event=_note_to_json(company.trigger_event),
        attempted_solutions=_notes_to_json(company.attempted_solutions),
        strategic_context=_note_to_json(company.strategic_context),
        last_activity_at=company.last_activity_at,
    ))


async def get_company(session: AsyncSession, company_id: str) -> Company | None:
    row = await session.get(CompanyORM, company_id)
    return _company_from_row(row) if row else None


async def list_companies(session: AsyncSession) -> list[Company]:
    rows = (await session.execute(select(CompanyORM))).scalars().all()
    return [_company_from_row(r) for r in rows]


# ── Contact ──────────────────────────────────────────────────────────────────

async def save_contact(session: AsyncSession, contact: Contact) -> None:
    await _upsert(session, ContactORM(
        id=contact.id, company_id=contact.company_id, name=contact.name,
        email=contact.email, phone=contact.phone, role=contact.role,
        sources=_sources_to_json(contact.sources), impacted_area=contact.impacted_area,
        seniority_tier=contact.seniority_tier,
    ))


async def list_contacts(session: AsyncSession, company_id: str) -> list[Contact]:
    rows = (await session.execute(select(ContactORM).where(ContactORM.company_id == company_id))).scalars().all()
    return [Contact(
        id=r.id, company_id=r.company_id, name=r.name, email=r.email,
        role=r.role, phone=r.phone, sources=_sources_from_json(r.sources),
        impacted_area=r.impacted_area, seniority_tier=r.seniority_tier,
    ) for r in rows]


# ── Opportunity ──────────────────────────────────────────────────────────────

def _opportunity_from_row(row: OpportunityORM) -> Opportunity:
    return Opportunity(
        id=row.id, company_id=row.company_id, type=row.type, vendor_id=row.vendor_id,
        product_id=row.product_id, service_id=row.service_id, opportunity_score=row.opportunity_score,
        financial_potential=row.financial_potential, strategic_score=row.strategic_score,
        confidence_score=row.confidence_score, evidence=row.evidence, justification=row.justification,
        sources=_sources_from_json(row.sources), status=OpportunityStatus(row.status),
        risk_flag=row.risk_flag, evidence_summary=row.evidence_summary,
        discovery_prompt=row.discovery_prompt, synced_at=_ensure_utc(row.synced_at),
    )


async def save_opportunity(session: AsyncSession, opportunity: Opportunity) -> None:
    await _upsert(session, OpportunityORM(
        id=opportunity.id, company_id=opportunity.company_id, type=opportunity.type,
        vendor_id=opportunity.vendor_id, product_id=opportunity.product_id, service_id=opportunity.service_id,
        opportunity_score=opportunity.opportunity_score, financial_potential=opportunity.financial_potential,
        strategic_score=opportunity.strategic_score, confidence_score=opportunity.confidence_score,
        evidence=opportunity.evidence, justification=opportunity.justification,
        sources=_sources_to_json(opportunity.sources), status=opportunity.status.value,
        risk_flag=opportunity.risk_flag, evidence_summary=opportunity.evidence_summary,
        discovery_prompt=opportunity.discovery_prompt, synced_at=opportunity.synced_at,
    ))


async def list_opportunities(session: AsyncSession, company_id: str | None = None) -> list[Opportunity]:
    query = select(OpportunityORM)
    if company_id is not None:
        query = query.where(OpportunityORM.company_id == company_id)
    rows = (await session.execute(query)).scalars().all()
    return [_opportunity_from_row(r) for r in rows]


# ── Portfolio ────────────────────────────────────────────────────────────────

def _portfolio_from_row(row: PortfolioORM) -> Portfolio:
    return Portfolio(
        id=row.id, company_id=row.company_id, vendor_ids=row.vendor_ids, product_ids=row.product_ids,
        service_ids=row.service_ids, relations=row.relations, notes=row.notes, updated_at=_ensure_utc(row.updated_at),
    )


async def save_portfolio(session: AsyncSession, portfolio: Portfolio) -> None:
    await _upsert(session, PortfolioORM(
        id=portfolio.id, company_id=portfolio.company_id, vendor_ids=portfolio.vendor_ids,
        product_ids=portfolio.product_ids, service_ids=portfolio.service_ids,
        relations=portfolio.relations, notes=portfolio.notes, updated_at=portfolio.updated_at,
    ))


async def get_portfolio_by_company(session: AsyncSession, company_id: str) -> Portfolio | None:
    row = (await session.execute(select(PortfolioORM).where(PortfolioORM.company_id == company_id))).scalar_one_or_none()
    return _portfolio_from_row(row) if row else None


# ── CompanySignal ────────────────────────────────────────────────────────────

async def save_company_signal(session: AsyncSession, signal: CompanySignal) -> None:
    await _upsert(session, CompanySignalORM(
        id=signal.id, company_id=signal.company_id, signal_type=signal.signal_type,
        evidence=signal.evidence, source=signal.source.model_dump(),
        confidence=signal.confidence, detected_at=signal.detected_at, status=signal.status,
    ))


async def list_company_signals(session: AsyncSession, company_id: str) -> list[CompanySignal]:
    rows = (await session.execute(select(CompanySignalORM).where(CompanySignalORM.company_id == company_id))).scalars().all()
    return [CompanySignal(
        id=r.id, company_id=r.company_id, signal_type=r.signal_type, evidence=r.evidence,
        source=SourceRef(**r.source), confidence=r.confidence,
        detected_at=_ensure_utc(r.detected_at), status=r.status,
    ) for r in rows]


# ── OpportunityStatusChange ──────────────────────────────────────────────────

async def save_opportunity_status_change(session: AsyncSession, change: OpportunityStatusChange) -> None:
    await _upsert(session, OpportunityStatusChangeORM(
        id=change.id, opportunity_id=change.opportunity_id,
        status=change.status.value, entered_at=change.entered_at,
    ))


async def list_opportunity_status_changes(session: AsyncSession, opportunity_id: str) -> list[OpportunityStatusChange]:
    rows = (await session.execute(
        select(OpportunityStatusChangeORM).where(OpportunityStatusChangeORM.opportunity_id == opportunity_id)
    )).scalars().all()
    return [OpportunityStatusChange(
        id=r.id, opportunity_id=r.opportunity_id,
        status=OpportunityStatus(r.status), entered_at=_ensure_utc(r.entered_at),
    ) for r in rows]


# ── CorrelationRule ──────────────────────────────────────────────────────────

async def save_rule(session: AsyncSession, rule: CorrelationRule) -> None:
    await _upsert(session, CorrelationRuleORM(
        id=rule.id, opportunity_type=rule.opportunity_type, justification=rule.justification,
        requires=rule.requires, absent=rule.absent,
        requires_category=rule.requires_category, absent_category=rule.absent_category,
        relation_type=rule.relation_type, opportunity_score=rule.opportunity_score,
        confidence_score=rule.confidence_score, active=rule.active,
        discovery_prompt=rule.discovery_prompt,
    ))


def _rule_from_row(row: CorrelationRuleORM) -> CorrelationRule:
    return CorrelationRule(
        id=row.id, opportunity_type=row.opportunity_type, justification=row.justification,
        requires=row.requires, absent=row.absent,
        requires_category=row.requires_category, absent_category=row.absent_category,
        relation_type=row.relation_type, opportunity_score=row.opportunity_score,
        confidence_score=row.confidence_score, active=row.active,
        discovery_prompt=row.discovery_prompt,
    )


async def list_rules(session: AsyncSession) -> list[CorrelationRule]:
    rows = (await session.execute(select(CorrelationRuleORM))).scalars().all()
    return [_rule_from_row(r) for r in rows]


async def list_active_rules(session: AsyncSession) -> list[CorrelationRule]:
    rows = (await session.execute(select(CorrelationRuleORM).where(CorrelationRuleORM.active == True))).scalars().all()  # noqa: E712
    return [_rule_from_row(r) for r in rows]
