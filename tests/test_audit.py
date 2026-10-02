"""Fase M — registro de auditoria geral (persistência)."""
import asyncio
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Company, Contact, Opportunity, OpportunityStatus, SourceRef  # noqa: E402
from core.repository import (  # noqa: E402
    apply_field_mapping_updates, list_audit_entries, save_company, save_contact, save_opportunity,
    update_company_renewal_date, update_contact_stance, update_opportunity_discovery,
    update_opportunity_qualification, update_opportunity_status,
)
from tests.test_persistence import _fresh_session_factory  # noqa: E402


def _run(coro_fn):
    async def wrapper():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            await coro_fn(session_factory)
    asyncio.run(wrapper())


def _opportunity(company):
    return Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])


def test_renewal_date_change_is_audited_once_and_same_value_is_not():
    async def body(sf):
        company = Company(name="Aurora")
        first = datetime(2026, 12, 1, tzinfo=timezone.utc)
        async with sf() as session:
            await save_company(session, company)
            await update_company_renewal_date(session, company.id, first, actor="rep-1")
            await update_company_renewal_date(session, company.id, first, actor="rep-1")  # no-op
            await update_company_renewal_date(session, company.id, datetime(2027, 1, 1, tzinfo=timezone.utc))
            entries = await list_audit_entries(session, company_id=company.id)
        assert len(entries) == 2
        newest, oldest = entries
        assert (oldest.field, oldest.old_value, oldest.actor) == ("renewal_date", None, "rep-1")
        assert oldest.new_value.startswith("2026-12-01")
        assert newest.old_value.startswith("2026-12-01") and newest.new_value.startswith("2027-01-01")
        assert newest.actor is None  # nunca inventado
    _run(body)


def test_qualification_audits_values_but_never_free_text_note():
    async def body(sf):
        company = Company(name="Aurora")
        opp = _opportunity(company)
        async with sf() as session:
            await save_company(session, company)
            await save_opportunity(session, opp)
            await update_opportunity_qualification(session, opp.id, "isolado", "critico_interno", "Fulano de Tal pediu urgência")
            await update_opportunity_qualification(session, opp.id, "parcial", "critico_interno", "Fulano de Tal pediu urgência")
            entries = await list_audit_entries(session, entity_type="opportunity", entity_id=opp.id)
        by_field = {(e.field, e.new_value) for e in entries}
        assert ("scope_note", "isolado") in by_field and ("scope_note", "parcial") in by_field
        assert ("criticality", "critico_interno") in by_field
        assert ("severity_note", "preenchido") in by_field
        assert sum(1 for e in entries if e.field == "criticality") == 1  # segunda chamada não mudou
        assert "Fulano" not in " ".join(f"{e.old_value} {e.new_value}" for e in entries)
        assert all(e.company_id == company.id for e in entries)
    _run(body)


def test_discovery_audits_only_markers_never_the_personal_text():
    async def body(sf):
        company = Company(name="Aurora")
        opp = _opportunity(company)
        secret = "Meta pessoal do João Silva na diretoria"
        async with sf() as session:
            await save_company(session, company)
            await save_opportunity(session, opp)
            await update_opportunity_discovery(session, opp.id, None, None, secret, actor="rep-1")
            await update_opportunity_discovery(session, opp.id, None, None, f"  {secret}  ")  # só espaços: no-op
            await update_opportunity_discovery(session, opp.id, None, None, secret + " (atualizado)")
            await update_opportunity_discovery(session, opp.id, None, None, "")
            entries = await list_audit_entries(session, entity_type="opportunity", entity_id=opp.id)
        assert [e.new_value for e in reversed(entries)] == ["preenchido", "alterado", "removido"]
        assert all(e.field == "champion_stake" for e in entries)
        assert "João" not in " ".join(f"{e.old_value} {e.new_value}" for e in entries)
    _run(body)


def test_sync_field_mapping_updates_are_audited_with_sync_actor_only_when_changed():
    async def body(sf):
        company = Company(name="Aurora")
        renewal = datetime(2026, 11, 1, tzinfo=timezone.utc)
        async with sf() as session:
            await save_company(session, company)
            await apply_field_mapping_updates(session, company.id, {"renewal_date": renewal, "industry": "Software"})
            await apply_field_mapping_updates(session, company.id, {"renewal_date": renewal, "industry": "Software"})  # igual
            await apply_field_mapping_updates(session, company.id, {"industry": "Serviços"})
            entries = await list_audit_entries(session, company_id=company.id)
        assert {(e.field, e.actor) for e in entries} == {("renewal_date", "sync"), ("industry", "sync")}
        assert len(entries) == 3
    _run(body)


def test_contact_stance_and_discovery_skip_are_audited():
    async def body(sf):
        company = Company(name="Aurora")
        contact = Contact(company_id=company.id, name="Ana")
        opp = _opportunity(company)
        async with sf() as session:
            await save_company(session, company)
            await save_contact(session, contact)
            await save_opportunity(session, opp)
            await update_contact_stance(session, contact.id, "champion", actor="rep-2")
            await update_opportunity_status(
                session, opp.id, OpportunityStatus.QUALIFIED,
                skip_discovery_reason="Cliente pediu proposta urgente por telefone", discovery_gate_enabled=True,
            )
            stance = await list_audit_entries(session, entity_type="contact", entity_id=contact.id)
            skip = await list_audit_entries(session, entity_type="opportunity", entity_id=opp.id)
        assert [(e.field, e.new_value, e.actor) for e in stance] == [("stance", "champion", "rep-2")]
        assert stance[0].company_id == company.id
        fields = {e.field: e for e in skip}
        assert fields["discovery_skipped"].new_value == "True"
        assert fields["discovery_skip_reason"].new_value == "preenchido"
        assert "proposta" not in str([(e.old_value, e.new_value) for e in skip])
    _run(body)
