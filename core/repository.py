"""
Repositório — ponte entre os modelos de domínio (Pydantic,
core/models.py) e as tabelas (SQLAlchemy, core/db_models.py).

Upsert via session.merge() (insere ou atualiza pela PK, sem exists-check
manual). Mapeamento Pydantic<->ORM fica explícito por entidade — 7 entidades
com forma idêntica de CRUD justificam esse tanto de repetição; um
Repository[T] genérico esconderia a diferença de campos entre elas.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_models import (
    CompanyORM, ContactORM, OpportunityORM, PortfolioORM, ProductORM, ServiceORM, VendorORM,
)
from core.models import (
    Company, Contact, Opportunity, OpportunityStatus, Portfolio, Product, Service, SourceRef, Vendor,
)


def _sources_to_json(sources: list[SourceRef]) -> list[dict]:
    return [s.model_dump() for s in sources]


def _sources_from_json(data: list[dict] | None) -> list[SourceRef]:
    return [SourceRef(**d) for d in (data or [])]


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
        status=product.status, related_service_ids=product.related_service_ids,
    ))


async def list_products(session: AsyncSession) -> list[Product]:
    rows = (await session.execute(select(ProductORM))).scalars().all()
    return [Product(
        id=r.id, vendor_id=r.vendor_id, name=r.name, aliases=r.aliases,
        description=r.description, status=r.status, related_service_ids=r.related_service_ids,
    ) for r in rows]


# ── Service ──────────────────────────────────────────────────────────────────

async def save_service(session: AsyncSession, service: Service) -> None:
    await _upsert(session, ServiceORM(
        id=service.id, name=service.name, description=service.description, status=service.status,
    ))


async def list_services(session: AsyncSession) -> list[Service]:
    rows = (await session.execute(select(ServiceORM))).scalars().all()
    return [Service(id=r.id, name=r.name, description=r.description, status=r.status) for r in rows]


# ── Company ──────────────────────────────────────────────────────────────────

def _company_from_row(row: CompanyORM) -> Company:
    return Company(
        id=row.id, name=row.name, legal_name=row.legal_name, website=row.website,
        is_customer=row.is_customer, customer_status=row.customer_status,
        sources=_sources_from_json(row.sources), created_at=_ensure_utc(row.created_at), updated_at=_ensure_utc(row.updated_at),
    )


async def save_company(session: AsyncSession, company: Company) -> None:
    await _upsert(session, CompanyORM(
        id=company.id, name=company.name, legal_name=company.legal_name, website=company.website,
        is_customer=company.is_customer, customer_status=company.customer_status,
        sources=_sources_to_json(company.sources), created_at=company.created_at, updated_at=company.updated_at,
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
        sources=_sources_to_json(contact.sources),
    ))


async def list_contacts(session: AsyncSession, company_id: str) -> list[Contact]:
    rows = (await session.execute(select(ContactORM).where(ContactORM.company_id == company_id))).scalars().all()
    return [Contact(
        id=r.id, company_id=r.company_id, name=r.name, email=r.email,
        role=r.role, phone=r.phone, sources=_sources_from_json(r.sources),
    ) for r in rows]


# ── Opportunity ──────────────────────────────────────────────────────────────

def _opportunity_from_row(row: OpportunityORM) -> Opportunity:
    return Opportunity(
        id=row.id, company_id=row.company_id, type=row.type, vendor_id=row.vendor_id,
        product_id=row.product_id, service_id=row.service_id, opportunity_score=row.opportunity_score,
        financial_potential=row.financial_potential, strategic_score=row.strategic_score,
        confidence_score=row.confidence_score, evidence=row.evidence, justification=row.justification,
        sources=_sources_from_json(row.sources), status=OpportunityStatus(row.status),
    )


async def save_opportunity(session: AsyncSession, opportunity: Opportunity) -> None:
    await _upsert(session, OpportunityORM(
        id=opportunity.id, company_id=opportunity.company_id, type=opportunity.type,
        vendor_id=opportunity.vendor_id, product_id=opportunity.product_id, service_id=opportunity.service_id,
        opportunity_score=opportunity.opportunity_score, financial_potential=opportunity.financial_potential,
        strategic_score=opportunity.strategic_score, confidence_score=opportunity.confidence_score,
        evidence=opportunity.evidence, justification=opportunity.justification,
        sources=_sources_to_json(opportunity.sources), status=opportunity.status.value,
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
