"""Tabelas SQLAlchemy — espelham core/models.py. Listas/dicts
(sources, evidence, aliases, relations) viram JSON — SQLite/SQLAlchemy serializa
automaticamente, sem precisar de tabela associativa pra isso aqui."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class VendorORM(Base):
    __tablename__ = "vendors"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)


class ProductORM(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    related_services: Mapped[list] = mapped_column(JSON, default=list)


class ServiceORM(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)


class CompanyORM(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    customer_status: Mapped[str | None] = mapped_column(String, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()
    rep_id: Mapped[str | None] = mapped_column(String, nullable=True)
    segment: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger_event: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempted_solutions: Mapped[list] = mapped_column(JSON, default=list)
    strategic_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(nullable=True)
    renewal_date: Mapped[datetime | None] = mapped_column(nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    annual_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deal_size_hint: Mapped[float | None] = mapped_column(Float, nullable=True)


class ContactORM(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    impacted_area: Mapped[str | None] = mapped_column(String, nullable=True)
    seniority_tier: Mapped[str | None] = mapped_column(String, nullable=True)


class OpportunityORM(Base):
    __tablename__ = "opportunities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    vendor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    service_id: Mapped[str | None] = mapped_column(String, nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    financial_potential: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    justification: Mapped[str | None] = mapped_column(String, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String)
    risk_flag: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    discovery_prompt: Mapped[str | None] = mapped_column(String, nullable=True)
    synced_at: Mapped[datetime] = mapped_column()
    first_detected_at: Mapped[datetime] = mapped_column()
    scope_note: Mapped[str | None] = mapped_column(String, nullable=True)
    criticality: Mapped[str | None] = mapped_column(String, nullable=True)
    severity_note: Mapped[str | None] = mapped_column(String, nullable=True)
    dismissal_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class PortfolioORM(Base):
    __tablename__ = "portfolios"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String, unique=True)
    vendor_ids: Mapped[list] = mapped_column(JSON, default=list)
    product_ids: Mapped[list] = mapped_column(JSON, default=list)
    service_ids: Mapped[list] = mapped_column(JSON, default=list)
    relations: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column()


class CompanySignalORM(Base):
    __tablename__ = "company_signals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String)
    signal_type: Mapped[str] = mapped_column(String)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    detected_at: Mapped[datetime] = mapped_column()
    status: Mapped[str] = mapped_column(String)


class OpportunityStatusChangeORM(Base):
    __tablename__ = "opportunity_status_changes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    entered_at: Mapped[datetime] = mapped_column()
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    dismissal_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class OpportunitySnapshotORM(Base):
    """Fase D — foto diária de cada oportunidade viva, recalculada no fim
    de todo `POST /sync` (nunca em tempo real a partir das tabelas
    transacionais, decisão de arquitetura do roadmap). `id` determinístico
    (`f"{opportunity_id}:{snapshot_date}"`) faz o upsert do dia ser
    idempotente — rodar `/sync` várias vezes no mesmo dia nunca duplica
    linha. `financial_potential`/`confidence_score` guardados separados
    (nunca pré-multiplicados) pra bruto e ponderado continuarem deriváveis
    da mesma linha, nunca dessincronizados."""
    __tablename__ = "opportunity_snapshots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String)
    snapshot_date: Mapped[date] = mapped_column(Date)
    stage: Mapped[str] = mapped_column(String)
    first_detected_at: Mapped[datetime] = mapped_column()
    financial_potential: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rep_id: Mapped[str | None] = mapped_column(String, nullable=True)
    segment: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    is_zombie: Mapped[bool] = mapped_column(Boolean, default=False)


class CorrelationRuleORM(Base):
    __tablename__ = "correlation_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_type: Mapped[str] = mapped_column(String)
    justification: Mapped[str] = mapped_column(String)
    requires: Mapped[list] = mapped_column(JSON, default=list)
    absent: Mapped[list] = mapped_column(JSON, default=list)
    requires_category: Mapped[list] = mapped_column(JSON, default=list)
    absent_category: Mapped[list] = mapped_column(JSON, default=list)
    relation_type: Mapped[str | None] = mapped_column(String, nullable=True)
    opportunity_score: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    discovery_prompt: Mapped[str | None] = mapped_column(String, nullable=True)


class RepTargetORM(Base):
    """Fase D, módulo 7 — id determinístico (`rep_target_id`, mesmo padrão
    de `_generate_opportunity_id` em opportunity_engine.py) a partir de
    (rep_id, period_type, period_key): cadastrar meta de novo pro mesmo
    rep+período é upsert, nunca duplicata."""
    __tablename__ = "rep_targets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    rep_id: Mapped[str] = mapped_column(String)
    period_type: Mapped[str] = mapped_column(String)
    period_key: Mapped[str] = mapped_column(String)
    target_amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column()


class ICPProfileORM(Base):
    """Fase E, módulo `icp-profile-store` — singleton (`id` sempre
    'icp_profile'), upsert via session.merge, nunca uma 2ª linha."""
    __tablename__ = "icp_profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    reference_product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    place_category: Mapped[str | None] = mapped_column(String, nullable=True)
    company_size_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    radius_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    search_origin_address: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column()


class FieldMappingORM(Base):
    """Fase F, módulo 3 (`field-mapping-store`) — id determinístico
    (`field_mapping_id`, mesmo padrão de `rep_target_id`) a partir de
    (provider_id, source_field_api_name): cadastrar mapeamento de novo
    pro mesmo campo é upsert, nunca duplicata. `provider_id` string
    genérica — nenhuma referência a Salesforce aqui.

    `UniqueConstraint(provider_id, role)` (achado da revisão de código do
    módulo 5): um papel só pode ter uma fonte por vez (decisão do Sales
    Engineer) — sem essa trava no banco, duas requisições concorrentes de
    reatribuição pro MESMO papel (ex.: duas abas) poderiam cada uma ler o
    mapeamento anterior, deletar, e inserir o próprio campo, deixando dois
    campos mapeados pro mesmo papel ao mesmo tempo. A trava faz a 2ª
    inserção falhar em vez de silenciosamente violar a garantia."""
    __tablename__ = "field_mappings"
    __table_args__ = (UniqueConstraint("provider_id", "role", name="uq_field_mappings_provider_role"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider_id: Mapped[str] = mapped_column(String)
    source_field_api_name: Mapped[str] = mapped_column(String)
    source_field_label: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
