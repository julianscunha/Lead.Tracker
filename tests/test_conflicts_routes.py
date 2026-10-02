"""Fase N — rotas de conflitos de dados."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Company, SourceRef  # noqa: E402
from core.normalization import ConflictProposal  # noqa: E402
from core.repository import get_company, record_reconciliation, save_company  # noqa: E402
from tests.test_routes_sync import _TempDb, client  # noqa: E402

BASE = "/modules/lead_tracker"


def _seed_conflict(db):
    company = Company(name="Acme Ltda", industry="Software", sources=[SourceRef(type="salesforce")])

    async def run():
        async with db.session_factory() as session:
            await save_company(session, company)
            await record_reconciliation(
                session, company.id, [], [ConflictProposal("industry", "Software", "salesforce", "Varejo", "csv")], "csv",
            )
    asyncio.run(run())
    return company


def test_list_open_conflicts_shows_company_name_and_both_candidates():
    with _TempDb() as db:
        company = _seed_conflict(db)
        body = client.get(f"{BASE}/field-conflicts").json()
        assert len(body) == 1 and body[0]["company_name"] == "Acme Ltda" and body[0]["field"] == "industry"
        assert {(c["source"], c["value"]) for c in body[0]["candidates"]} == {("salesforce", "Software"), ("csv", "Varejo")}
        assert body[0]["company_id"] == company.id


def test_resolve_applies_chosen_value_records_actor_and_removes_from_open_list():
    with _TempDb() as db:
        company = _seed_conflict(db)
        conflict_id = client.get(f"{BASE}/field-conflicts").json()[0]["id"]
        resp = client.post(f"{BASE}/field-conflicts/{conflict_id}/resolve", json={"chosen_source": "csv", "rep_id": "rep-3"})
        assert resp.status_code == 200 and resp.json()["resolved_source"] == "csv"
        assert client.get(f"{BASE}/field-conflicts").json() == []

        async def check():
            async with db.session_factory() as session:
                return (await get_company(session, company.id)).industry
        assert asyncio.run(check()) == "Varejo"
        audit = client.get(f"{BASE}/companies/{company.id}/audit").json()
        assert [(e["field"], e["old_value"], e["new_value"], e["actor"]) for e in audit] == [("industry", "Software", "Varejo", "rep-3")]


def test_resolve_rejects_unknown_source_already_resolved_and_reserved_actor():
    with _TempDb() as db:
        _seed_conflict(db)
        conflict_id = client.get(f"{BASE}/field-conflicts").json()[0]["id"]
        url = f"{BASE}/field-conflicts/{conflict_id}/resolve"
        assert client.post(url, json={"chosen_source": "hubspot"}).status_code == 404
        assert client.post(url, json={"chosen_source": "csv", "rep_id": "sync:csv"}).status_code == 422
        assert client.post(url, json={"chosen_source": "csv"}).status_code == 200
        assert client.post(url, json={"chosen_source": "salesforce"}).status_code == 404  # já resolvido
