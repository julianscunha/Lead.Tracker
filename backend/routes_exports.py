"""
Rotas de exportação e rascunho de e-mail.

Contrato: input validado na borda (pydantic), sem estado — o chamador manda
os dados já filtrados/ordenados, a rota só transforma em PDF/Excel/rascunho.
Erro técnico nunca vaza cru pro cliente (CLAUDE.md 'Error handling'). Todo
DomainError vira HTTPException pela mesma tabela categoria->status,
não uma regra por rota.
"""
from __future__ import annotations

import logging
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.business_case_prose import apply_ai_prose
from ai.email_draft import generate_email_draft
from ai.factory import create_ai_provider
from core.config import load_env
from backend.db_session import session_factory
from backend.http_errors import raise_http as _raise_http
from core.business_case import assemble_business_case
from core.dashboard_metrics import DashboardKPIs
from core.errors import DomainError, ErrorCategory
from backend.blocks import block_error, find_block
from core.repository import get_company, get_opportunity, get_product, get_service, list_contacts
from exports.excel import opportunities_excel
from exports.pdf import business_case_pdf, executive_pdf, opportunities_pdf
from exports.types import OpportunityExportRow

_MODULE_ROOT = Path(__file__).parent.parent

log = logging.getLogger(__name__)

router = APIRouter(tags=["lead_tracker-exports"])


class OpportunityRowSchema(BaseModel):
    company_name: str
    is_customer: bool
    opportunity_score: float | None = None
    financial_potential: float | None = None
    product: str | None = None
    service: str | None = None
    priority: str
    sources: list[str] = []

    def to_export_row(self) -> OpportunityExportRow:
        return OpportunityExportRow(**self.model_dump())


class OpportunitiesPdfRequest(BaseModel):
    rows: list[OpportunityRowSchema]
    filters_summary: str = "sem filtro"


class KpisSchema(BaseModel):
    opportunities_identified: int
    customers_analyzed: int
    prospects_analyzed: int
    financial_potential_total: float
    product_opportunities: int
    service_opportunities: int
    top_vendor: str | None = None
    top_service: str | None = None


class ExecutivePdfRequest(BaseModel):
    kpis: KpisSchema
    top_opportunities: list[OpportunityRowSchema]
    insights: str
    period_label: str
    vendor_distribution: list[tuple[str, int]] = []
    funnel_counts: dict[str, int] = {}


class EmailDraftRequest(BaseModel):
    # Fase L: o servidor carrega a oportunidade/empresa e checa "não contatar" — sem o id não há como checar.
    opportunity_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    contact_id: str | None = Field(default=None, max_length=64)
    company_name: str
    opportunity_type: str
    evidence: list[str] = []
    justification: str | None = None
    portfolio: dict = {}
    # Fase G, módulo 1 — opcional: quando ausente, usa `justification` como
    # motivo principal (mesmo default de generate_email_draft).
    primary_reason: str | None = None
    # Fase G, módulo 3 — Company.is_customer, decide qual das duas variações
    # de tom o prompt usa (default False = tom de prospecção fria).
    is_customer: bool = False


@router.post("/exports/pdf")
async def export_opportunities_pdf(body: OpportunitiesPdfRequest) -> Response:
    rows = [r.to_export_row() for r in body.rows]
    try:
        pdf_bytes = opportunities_pdf(rows, body.filters_summary, datetime.now(timezone.utc))
    except DomainError as exc:
        _raise_http(exc)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.post("/exports/excel")
async def export_opportunities_excel(body: OpportunitiesPdfRequest) -> Response:
    rows = [r.to_export_row() for r in body.rows]
    try:
        excel_bytes = opportunities_excel(rows)
    except DomainError as exc:
        _raise_http(exc)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/exports/executive-pdf")
async def export_executive_pdf(body: ExecutivePdfRequest) -> Response:
    kpis = DashboardKPIs(**body.kpis.model_dump())
    top = [r.to_export_row() for r in body.top_opportunities]
    try:
        pdf_bytes = executive_pdf(
            kpis, top, body.insights, datetime.now(timezone.utc),
            body.period_label, body.vendor_distribution, body.funnel_counts,
        )
    except DomainError as exc:
        _raise_http(exc)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.post("/email-draft")
async def email_draft(body: EmailDraftRequest) -> dict:
    env = load_env(_MODULE_ROOT / ".env")
    api_key = env.get("AI_API_KEY", "")
    if not api_key:
        _raise_http(DomainError(
            ErrorCategory.CONFIGURATION,
            "IA não configurada.",
            "Configure a chave de IA na aba Configurações (seção Inteligência Artificial) para gerar rascunhos.",
        ))

    try:
        async with session_factory() as session:
            opp = await get_opportunity(session, body.opportunity_id)
            if opp is None:
                raise _not_found("Oportunidade")
            contact = None
            if body.contact_id:
                contact = next((c for c in await list_contacts(session, opp.company_id) if c.id == body.contact_id), None)
                if contact is None:
                    raise DomainError(ErrorCategory.INVALID_DATA, "Esse contato não pertence à empresa da oportunidade.")
            block = await find_block(session, opp.company_id, contact, "email")
        if block is not None:
            raise block_error(block, "Não gere rascunho para esse alvo. Se a situação mudou, reative o contato primeiro.", contact)
    except DomainError as exc:
        _raise_http(exc)

    provider = create_ai_provider(env.get("AI_PROVIDER", ""), api_key, env.get("AI_MODEL", ""))
    try:
        draft = await generate_email_draft(
            provider, body.company_name, body.opportunity_type,
            body.evidence, body.justification, body.portfolio,
            primary_reason=body.primary_reason, is_customer=body.is_customer,
        )
    except DomainError as exc:
        _raise_http(exc)

    return {
        "subject": draft.subject, "greeting": draft.greeting, "body": draft.body, "cta": draft.cta,
        "primary_reason": draft.primary_reason, "differentiator": draft.differentiator, "ps": draft.ps,
    }


class BusinessCaseRequest(BaseModel):
    # Só o id vem do cliente; tudo o mais é carregado no servidor.
    model_config = ConfigDict(extra="forbid")
    opportunity_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    usar_ia: bool = False


def _not_found(what: str) -> DomainError:
    return DomainError(ErrorCategory.NOT_FOUND, f"{what} não encontrada.", "Atualize a lista e tente novamente.")


def _pdf_filename(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_name).strip("-")[:40] or "empresa"
    return f"business-case-{slug}.pdf"


@router.post("/exports/business-case")
async def export_business_case(body: BusinessCaseRequest) -> Response:
    try:
        async with session_factory() as session:
            opp = await get_opportunity(session, body.opportunity_id)
            if opp is None:
                raise _not_found("Oportunidade")
            company = await get_company(session, opp.company_id)
            if company is None:
                raise _not_found("Empresa")
            if opp.product_id:
                item = await get_product(session, opp.product_id)
            elif opp.service_id:
                item = await get_service(session, opp.service_id)
            else:
                raise DomainError(
                    ErrorCategory.INVALID_DATA,
                    "Esta oportunidade ainda não está ligada a um produto ou serviço do portfólio, então não dá para montar o business case.",
                    "Ligue a oportunidade a um item do portfólio e tente novamente.",
                )
            if item is None:
                raise _not_found("Produto ou serviço da oportunidade")
        # sessão fechada: nada de banco aberto durante a chamada de IA
        case = assemble_business_case(opp, company, item, datetime.now(timezone.utc).date())

        provider = None
        if body.usar_ia:
            env = load_env(_MODULE_ROOT / ".env")
            api_key = env.get("AI_API_KEY", "")
            if api_key:
                try:
                    provider = create_ai_provider(env.get("AI_PROVIDER", ""), api_key, env.get("AI_MODEL", ""))
                except DomainError:
                    provider = None  # IA opcional: degrada para o texto determinístico
        result = await apply_ai_prose(case, provider, opp=opp, company=company, item=item)
        pdf = await run_in_threadpool(business_case_pdf, result.case, datetime.now(timezone.utc))
    except DomainError as exc:
        _raise_http(exc)

    log.info("business_case opportunity_id=%s fonte_prosa=%s", body.opportunity_id, result.fonte_prosa)
    filename = _pdf_filename(company.name)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Prosa-Fonte": result.fonte_prosa,
    })
