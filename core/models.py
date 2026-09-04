"""
Modelos de domínio.

Entidades internas do Lead.Tracker, independentes de qualquer provider ou
integração externa (Salesforce, website, etc.).

Vendor/Source/tipo de oportunidade ficam como `str` livre (não Enum fechado):
o núcleo deve permanecer genérico e não travar em fabricantes ou fontes
específicas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid4())


class SourceRef(BaseModel):
    """Rastreabilidade de origem de uma informação (§02 'Fontes')."""
    type: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class ContextNote(BaseModel):
    """Fato registrado com fonte e data — nunca texto solto sem
    rastreabilidade. Reaproveitado onde quer que um campo precise de
    'porquê' além do valor (trigger_event, attempted_solutions, etc.)."""
    text: str
    source: SourceRef
    observed_at: datetime = Field(default_factory=_now)


class Company(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    legal_name: str | None = None
    website: str | None = None
    is_customer: bool = False
    customer_status: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    # Fundação de dado (Fase B do roadmap) — todos None/vazios até uma fonte
    # real preencher; nenhum valor é inventado aqui.
    rep_id: str | None = None
    segment: str | None = None
    region: str | None = None
    trigger_event: ContextNote | None = None
    attempted_solutions: list[ContextNote] = Field(default_factory=list)
    strategic_context: ContextNote | None = None


class Contact(BaseModel):
    """Pessoa de contato em uma empresa. Necessário pelo contrato de provider
    (fetch_contacts)."""
    id: str = Field(default_factory=_new_id)
    company_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    # Quem sente o impacto de um gap detectado — string livre (ex.:
    # "operações/TI", "compliance/risco"), distinto do cargo formal (`role`).
    impacted_area: str | None = None


class Vendor(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str


class ProductRelation(BaseModel):
    """Relação tipada entre um Product e um Service — convenção, não Enum
    fechado (núcleo genérico): 'prerequisite' | 'complementary' | 'substitute'."""
    service_id: str
    relation_type: str = "complementary"


class Product(BaseModel):
    id: str = Field(default_factory=_new_id)
    vendor_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    status: str | None = None
    category: str | None = None
    related_services: list[ProductRelation] = Field(default_factory=list)


class Service(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    description: str | None = None
    status: str | None = None
    category: str | None = None


class OpportunityStatus(str, Enum):
    """Fluxo fixo de status (§CLAUDE.md 'Opportunity status flow')."""
    DETECTED = "detected"
    QUALIFIED = "qualified"
    REVIEWED = "reviewed"
    CONTACTED = "contacted"
    OPPORTUNITY = "opportunity"
    DISMISSED = "dismissed"


class Opportunity(BaseModel):
    id: str = Field(default_factory=_new_id)
    company_id: str
    type: str
    vendor_id: str | None = None
    product_id: str | None = None
    service_id: str | None = None
    opportunity_score: float | None = None
    financial_potential: float | None = None
    strategic_score: float | None = None
    confidence_score: float | None = None
    evidence: list[str] = Field(default_factory=list)
    justification: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    status: OpportunityStatus = OpportunityStatus.DETECTED


class Portfolio(BaseModel):
    id: str = Field(default_factory=_new_id)
    company_id: str
    vendor_ids: list[str] = Field(default_factory=list)
    product_ids: list[str] = Field(default_factory=list)
    service_ids: list[str] = Field(default_factory=list)
    relations: list[dict] = Field(default_factory=list)
    notes: str | None = None
    updated_at: datetime = Field(default_factory=_now)


class CompanySignal(BaseModel):
    """Sinal de expansão/risco em uma empresa (renovação próxima, troca de
    contato-chave, adoção parcial, ...) — alimenta o mesmo motor de regras
    da Opportunity, nunca um motor paralelo. `signal_type` é string aberta:
    o núcleo não fecha a lista de tipos possíveis."""
    id: str = Field(default_factory=_new_id)
    company_id: str
    signal_type: str
    evidence: list[str] = Field(default_factory=list)
    source: SourceRef
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    detected_at: datetime = Field(default_factory=_now)
    status: str = "open"  # open | resolved | dismissed


class OpportunityStatusChange(BaseModel):
    """Histórico de transição de status de uma Opportunity — pré-requisito
    de qualquer métrica de tempo parado/velocity (Fase D)."""
    id: str = Field(default_factory=_new_id)
    opportunity_id: str
    status: OpportunityStatus
    entered_at: datetime = Field(default_factory=_now)
