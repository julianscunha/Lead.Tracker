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

from pydantic import BaseModel, Field, model_validator


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
    # Preenchido por regra de pré-requisito (relation_type="prerequisite"):
    # produto vendido sem o pré-requisito é risco técnico, não oportunidade
    # de venda — string livre descrevendo o risco, nunca um novo Opportunity.
    risk_flag: str | None = None
    # Fase C, Fatia 3 — princípio 2 (evidência = fato + implicação + fonte +
    # data). Nunca substitui evidence/justification/sources, só compõe uma
    # frase legível a partir deles.
    evidence_summary: str | None = None
    discovery_prompt: str | None = None
    synced_at: datetime = Field(default_factory=_now)


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
    signal_type: str  # convenção: nunca reusar um vendor/product/service id — motor de regras trata os dois no mesmo conjunto de "itens presentes"
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


class RuleError(Exception):
    """Regra de correlação mal definida (ex.: sem nenhum mecanismo de
    evidência) — nunca vira Opportunity, sempre barrada na criação."""


class CorrelationRule(BaseModel):
    """
    Regra de correlação determinística (Fase C do roadmap) — 3 tipos no
    total, nunca mais (resistir a pedido de motor tipo query language):

    1. Presença/ausência simples: `requires`/`absent` (ids de vendor/
       product/service no portfólio) — forma original, já existia.
    2. Por categoria: `requires_category`/`absent_category` (categoria de
       Product/Service) — generaliza sem exigir listar item por item.
    3. Por relação tipada: `relation_type` ("prerequisite" ou "substitute",
       de `ProductRelation`) — "substitute" gera oportunidade de
       consolidação; "prerequisite" sinaliza `Opportunity.risk_flag`, nunca
       inventa oportunidade de venda.

    Uma regra usa só UM desses três mecanismos por vez.
    """
    id: str = Field(default_factory=_new_id)
    opportunity_type: str
    justification: str
    requires: list[str] = Field(default_factory=list)
    absent: list[str] = Field(default_factory=list)
    requires_category: list[str] = Field(default_factory=list)
    absent_category: list[str] = Field(default_factory=list)
    relation_type: str | None = None
    opportunity_score: float = 1.0
    confidence_score: float = 1.0
    active: bool = True
    # Pergunta que o vendedor deveria fazer pra confirmar a causa raiz —
    # nunca a resposta (princípio 2 do roadmap). Opcional, por regra.
    discovery_prompt: str | None = None

    @model_validator(mode="after")
    def _requires_exactly_one_evidence_mechanism(self) -> "CorrelationRule":
        mechanisms = [
            bool(self.requires or self.absent),
            bool(self.requires_category or self.absent_category),
            bool(self.relation_type),
        ]
        used = sum(mechanisms)
        if used == 0:
            raise RuleError(
                f"regra '{self.id}': precisa de 'requires', 'requires_category' "
                "ou 'relation_type' — oportunidade sem evidência"
            )
        if used > 1:
            raise RuleError(
                f"regra '{self.id}': só pode usar UM mecanismo por vez — "
                "item, categoria OU relação, nunca combinados"
            )
        if self.relation_type is not None and self.relation_type not in ("prerequisite", "substitute"):
            # Convenção de valor, não Enum fechado (núcleo genérico) — mas
            # só essas duas o motor sabe avaliar hoje; qualquer outra vira
            # regra "morta" silenciosa (nunca dispara, nunca avisa ninguém).
            raise RuleError(
                f"regra '{self.id}': relation_type '{self.relation_type}' não é avaliado pelo motor "
                "— use 'prerequisite' ou 'substitute'"
            )
        return self
