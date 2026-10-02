"""Helpers só de teste: escrita/leitura direta de fixtures que a aplicação não usa.
`save_opportunity_status_change` grava fora da transação de `update_opportunity_status`
(TOCTOU) — por isso nunca vive no código de produção."""
from core.db_models import CompanySignalORM, OpportunityStatusChangeORM
from core.models import CompanySignal, DismissalReason, OpportunityStatus, OpportunityStatusChange
from core.repository import _ensure_utc, _upsert
from sqlalchemy import select


async def save_company_signal(session, signal: CompanySignal) -> None:
    await _upsert(session, CompanySignalORM(
        id=signal.id, company_id=signal.company_id, signal_type=signal.signal_type,
        evidence=signal.evidence, source=signal.source.model_dump(),
        confidence=signal.confidence, detected_at=signal.detected_at, status=signal.status,
    ))


async def save_opportunity_status_change(session, change: OpportunityStatusChange) -> None:
    await _upsert(session, OpportunityStatusChangeORM(
        id=change.id, opportunity_id=change.opportunity_id,
        status=change.status.value, entered_at=change.entered_at, note=change.note,
        dismissal_reason=change.dismissal_reason.value if change.dismissal_reason else None,
    ))


async def list_opportunity_status_changes(session, opportunity_id: str) -> list[OpportunityStatusChange]:
    rows = (await session.execute(
        select(OpportunityStatusChangeORM).where(OpportunityStatusChangeORM.opportunity_id == opportunity_id)
    )).scalars().all()
    return [OpportunityStatusChange(
        id=r.id, opportunity_id=r.opportunity_id,
        status=OpportunityStatus(r.status), entered_at=_ensure_utc(r.entered_at), note=r.note,
        dismissal_reason=DismissalReason(r.dismissal_reason) if r.dismissal_reason else None,
    ) for r in rows]
