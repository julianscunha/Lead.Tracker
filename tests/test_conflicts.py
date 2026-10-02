"""Fase N — conflito entre fontes: persistência e ligação no sync."""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.settings import SourceDescriptor  # noqa: E402
from backend.sync import sync_source  # noqa: E402
from core.models import Company, SourceRef  # noqa: E402
from core.repository import (  # noqa: E402
    get_company, list_audit_entries, list_companies, list_field_conflicts, resolve_field_conflict,
)
from tests.test_persistence import _fresh_session_factory  # noqa: E402
from tests.test_sync import _FakeProvider  # noqa: E402


def _source(source_id, companies):
    provider = _FakeProvider(companies)
    return SourceDescriptor(id=source_id, label=source_id, enabled_key=None, implemented=True, build=lambda env: provider)


def _run(coro_fn):
    async def wrapper():
        with tempfile.TemporaryDirectory() as tmp:
            await coro_fn(await _fresh_session_factory(tmp))
    asyncio.run(wrapper())


def _acme(industry, source, **kw):
    return Company(name="Acme", website="https://acme.com.br", industry=industry, sources=[SourceRef(type=source)], **kw)


def test_second_sync_from_same_source_refreshes_value_and_audits_it():
    async def body(sf):
        await sync_source(sf, _source("salesforce", [_acme("Software", "salesforce")]), {})
        await sync_source(sf, _source("salesforce", [_acme("Serviços", "salesforce")]), {})
        async with sf() as session:
            companies = await list_companies(session)
            entries = await list_audit_entries(session, company_id=companies[0].id)
            conflicts = await list_field_conflicts(session)
        assert len(companies) == 1 and companies[0].industry == "Serviços"
        assert conflicts == []
        assert [(e.field, e.old_value, e.new_value, e.actor) for e in entries] == [
            ("industry", "Software", "Serviços", "sync:salesforce")]
    _run(body)


def test_other_source_disagreeing_opens_one_conflict_and_never_overwrites():
    async def body(sf):
        await sync_source(sf, _source("salesforce", [_acme("Software", "salesforce")]), {})
        for _ in range(2):  # repetir o sync não duplica o conflito
            await sync_source(sf, _source("csv", [_acme("Varejo", "csv")]), {})
        async with sf() as session:
            company = (await list_companies(session))[0]
            conflicts = await list_field_conflicts(session)
        assert company.industry == "Software"
        assert len(conflicts) == 1 and conflicts[0].field == "industry"
        assert {(c.source, c.value) for c in conflicts[0].candidates} == {("salesforce", "Software"), ("csv", "Varejo")}
    _run(body)


def test_resolving_applies_value_audits_and_does_not_reopen_on_next_sync():
    async def body(sf):
        await sync_source(sf, _source("salesforce", [_acme("Software", "salesforce")]), {})
        await sync_source(sf, _source("csv", [_acme("Varejo", "csv")]), {})
        async with sf() as session:
            conflict = (await list_field_conflicts(session))[0]
            resolved = await resolve_field_conflict(session, conflict.id, "salesforce", actor="rep-1")
            again = await resolve_field_conflict(session, conflict.id, "csv", actor="rep-1")  # já resolvido
        assert resolved.status == "resolved" and resolved.resolved_source == "salesforce" and again is None
        await sync_source(sf, _source("csv", [_acme("Varejo", "csv")]), {})  # mesmo valor rejeitado
        async with sf() as session:
            assert await list_field_conflicts(session) == []
        await sync_source(sf, _source("csv", [_acme("Indústria", "csv")]), {})  # valor novo reabre
        async with sf() as session:
            assert len(await list_field_conflicts(session)) == 1
    _run(body)


def test_choosing_the_other_source_writes_its_value_audits_and_transfers_ownership():
    async def body(sf):
        await sync_source(sf, _source("salesforce", [_acme("Software", "salesforce")]), {})
        await sync_source(sf, _source("csv", [_acme("Varejo", "csv")]), {})
        async with sf() as session:
            conflict = (await list_field_conflicts(session))[0]
            await resolve_field_conflict(session, conflict.id, "csv", actor="rep-9")
            company = (await list_companies(session))[0]
            entries = await list_audit_entries(session, company_id=company.id)
        assert company.industry == "Varejo" and company.field_sources["industry"] == "csv"
        assert [(e.old_value, e.new_value, e.actor) for e in entries] == [("Software", "Varejo", "rep-9")]
        # a CSV agora é a dona: novo valor dela atualiza, e o Salesforce passa a ser quem diverge
        await sync_source(sf, _source("csv", [_acme("Comércio", "csv")]), {})
        async with sf() as session:
            assert (await get_company(session, company.id)).industry == "Comércio"
    _run(body)


def test_company_without_field_sources_in_existing_db_is_derived_not_flooded_with_conflicts():
    async def body(sf):
        async with sf() as session:
            from core.repository import save_company
            await save_company(session, _acme("Software", "salesforce"))  # field_sources vazio, como em instalação antiga
        await sync_source(sf, _source("salesforce", [_acme("Software", "salesforce")]), {})
        async with sf() as session:
            assert await list_field_conflicts(session) == []
    _run(body)
