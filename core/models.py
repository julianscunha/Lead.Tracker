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


class Vendor(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str


class Product(BaseModel):
    id: str = Field(default_factory=_new_id)
    vendor_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    status: str | None = None
    related_service_ids: list[str] = Field(default_factory=list)


class Service(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    description: str | None = None
    status: str | None = None


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
