"""
Rotas de exportação e rascunho de e-mail.

Contrato: input validado na borda (pydantic), sem estado — o chamador manda
os dados já filtrados/ordenados, a rota só transforma em PDF/Excel/rascunho.
Erro técnico nunca vaza cru pro cliente (CLAUDE.md 'Error handling'). Todo
DomainError vira HTTPException pela mesma tabela categoria->status,
não uma regra por rota.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.email_draft import generate_email_draft
from ai.factory import create_ai_provider
from core.config import load_env
from core.dashboard_metrics import DashboardKPIs
from core.errors import DomainError, ErrorCategory
from exports.excel import opportunities_excel
from exports.pdf import executive_pdf, opportunities_pdf
from exports.types import OpportunityExportRow

_MODULE_ROOT = Path(__file__).parent.parent

router = APIRouter(tags=["lead_tracker-exports"])

_STATUS_BY_CATEGORY = {
    ErrorCategory.CONFIGURATION: 503,
    ErrorCategory.AUTHENTICATION: 502,
    ErrorCategory.CONNECTIVITY: 502,
    ErrorCategory.TIMEOUT: 504,
    ErrorCategory.API_LIMIT: 429,
    ErrorCategory.INTEGRATION: 502,
    ErrorCategory.INVALID_DATA: 422,
    ErrorCategory.AI: 502,
    ErrorCategory.EXPORT: 500,
}


def _raise_http(exc: DomainError) -> None:
    raise HTTPException(status_code=_STATUS_BY_CATEGORY.get(exc.category, 500), detail=str(exc)) from exc


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
    company_name: str
    opportunity_type: str
    evidence: list[str] = []
    justification: str | None = None
    portfolio: dict = {}


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
            "Defina AI_API_KEY nas configurações do módulo para gerar rascunhos.",
        ))

    provider = create_ai_provider(env.get("AI_PROVIDER", ""), api_key)
    try:
        draft = await generate_email_draft(
            provider, body.company_name, body.opportunity_type,
            body.evidence, body.justification, body.portfolio,
        )
    except DomainError as exc:
        _raise_http(exc)

    return {"subject": draft.subject, "greeting": draft.greeting, "body": draft.body, "cta": draft.cta}
