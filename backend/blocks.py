"""Fase L — "não contatar" aplicado nas rotas (única fonte do texto e da checagem)."""
from __future__ import annotations

from core.errors import DomainError, ErrorCategory
from core.models import Contact, DoNotContact
from core.opportunity_engine import find_active_block, normalize_channel
from core.repository import list_do_not_contact

REASON_LABEL = {
    "requested_by_contact": "o contato pediu para não ser contatado",
    "invalid_contact_data": "os dados de contato são inválidos",
    "rep_decision": "decisão do representante",
    "other": "outro motivo",
}


def is_ambiguous(entry: DoNotContact, contact: Contact | None) -> bool:
    """Bloqueio de um contato específico achado SEM contato escolhido na ação."""
    return contact is None and (entry.contact_id is not None or entry.contact_email is not None)


def block_error(entry: DoNotContact, hint: str = "", contact: Contact | None = None) -> DomainError:
    """Nunca inclui `comment`/`lift_reason` (podem ter dado pessoal)."""
    if is_ambiguous(entry, contact):
        return DomainError(
            ErrorCategory.INVALID_DATA,
            "Há contato desta empresa marcado como \"não contatar\": escolha para qual contato é esta ação.",
            hint or "Selecione o contato e tente de novo.",
        )
    who = "Esse contato" if entry.contact_id or entry.contact_email else "Essa empresa"
    where = f" no canal {entry.channel}" if entry.channel else ""
    return DomainError(
        ErrorCategory.INVALID_DATA,
        f'{who} está marcado como "não contatar"{where}: {REASON_LABEL.get(entry.reason.value, "outro motivo")}.',
        hint or 'Se a situação mudou, reative o contato na seção "Não contatar" da oportunidade.',
    )


async def find_block(session, company_id: str, contact: Contact | None, channel: str | None) -> DoNotContact | None:
    entries = await list_do_not_contact(session, active_only=True)
    found = find_active_block(
        entries, company_id, contact.id if contact else None, contact.email if contact else None, channel,
    )
    if found is not None or contact is not None:
        return found
    # Sem contato escolhido: não dá pra afirmar que o alvo NÃO é o contato bloqueado. Conservador:
    # qualquer bloqueio ativo de contato desta empresa, no canal, impede a ação até escolher o contato.
    wanted = normalize_channel(channel)
    return next((
        e for e in entries
        if e.company_id == company_id and (e.contact_id or e.contact_email)
        and (e.channel is None or wanted is None or normalize_channel(e.channel) == wanted)
    ), None)
