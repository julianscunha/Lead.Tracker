"""Fase M — rotas de auditoria e autoria opcional nas edições."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Company, Opportunity, SourceRef  # noqa: E402
from core.repository import save_company, save_opportunity  # noqa: E402
from tests.test_routes_sync import _TempDb, client  # noqa: E402

BASE = "/modules/lead_tracker"


def _seed(db, with_second_opportunity=False):
    company = Company(name="Aurora Sistemas")
    opp = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])
    other = Opportunity(company_id=company.id, type="up-sell", sources=[SourceRef(type="rule_engine")])

    async def run():
        async with db.session_factory() as session:
            await save_company(session, company)
            await save_opportunity(session, opp)
            if with_second_opportunity:
                await save_opportunity(session, other)
    asyncio.run(run())
    return company, opp, other


def test_edits_leave_audit_trail_with_optional_self_declared_actor():
    with _TempDb() as db:
        company, opp, _ = _seed(db)
        client.patch(f"{BASE}/opportunities/{opp.id}", json={"scope_note": "isolado", "criticality": "nao_critico", "rep_id": "rep-7"})
        client.patch(f"{BASE}/opportunities/{opp.id}/discovery", json={"champion_stake": "Segredo pessoal do contato"})
        client.patch(f"{BASE}/companies/{company.id}/renewal-date", json={"renewal_date": "2026-12-01T00:00:00Z", "rep_id": "rep-7"})
        entries = client.get(f"{BASE}/opportunities/{opp.id}/audit").json()
        by_field = {e["field"]: e for e in entries}
        assert by_field["scope_note"]["actor"] == "rep-7" and by_field["scope_note"]["new_value"] == "isolado"
        assert by_field["renewal_date"]["entity_type"] == "company" and by_field["renewal_date"]["actor"] == "rep-7"
        assert by_field["champion_stake"]["actor"] is None  # sem rep_id: não identificado, nunca inventado
        assert "Segredo" not in str(entries)
        assert [e["changed_at"] for e in entries] == sorted((e["changed_at"] for e in entries), reverse=True)


def test_opportunity_audit_excludes_other_opportunities_but_company_audit_has_all():
    with _TempDb() as db:
        company, opp, other = _seed(db, with_second_opportunity=True)
        client.patch(f"{BASE}/opportunities/{opp.id}", json={"scope_note": "parcial"})
        client.patch(f"{BASE}/opportunities/{other.id}", json={"scope_note": "generalizado"})
        client.patch(f"{BASE}/companies/{company.id}/renewal-date", json={"renewal_date": "2026-12-01T00:00:00Z"})
        mine = client.get(f"{BASE}/opportunities/{opp.id}/audit").json()
        assert {e["new_value"] for e in mine if e["field"] == "scope_note"} == {"parcial"}
        assert any(e["field"] == "renewal_date" for e in mine)  # empresa entra
        everything = client.get(f"{BASE}/companies/{company.id}/audit").json()
        assert {e["new_value"] for e in everything if e["field"] == "scope_note"} == {"parcial", "generalizado"}


def test_audit_routes_return_friendly_404_for_unknown_ids():
    with _TempDb():
        assert client.get(f"{BASE}/opportunities/inexistente/audit").status_code == 404
        assert client.get(f"{BASE}/companies/inexistente/audit").status_code == 404
