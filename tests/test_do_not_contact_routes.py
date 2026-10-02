"""Fase L — "não contatar" aplicado nas rotas (sugestão, toque, rascunho, contatos)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import routes_exports  # noqa: E402
from core.models import Company, Contact, Opportunity, OutreachTouch, SourceRef  # noqa: E402
from core.repository import save_company, save_contact, save_opportunity, save_outreach_touch  # noqa: E402
from tests.test_routes_sync import _TempDb, client  # noqa: E402

BASE = "/modules/lead_tracker"


def _seed(db, with_touch=False):
    company = Company(name="Aurora Sistemas")
    ana = Contact(company_id=company.id, name="Ana", email="Ana@Aurora.com", role="Diretora")
    bia = Contact(company_id=company.id, name="Bia", email="bia@aurora.com")
    opp = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

    async def run():
        async with db.session_factory() as session:
            await save_company(session, company)
            await save_contact(session, ana)
            await save_contact(session, bia)
            await save_opportunity(session, opp)
            if with_touch:
                await save_outreach_touch(session, OutreachTouch(
                    opportunity_id=opp.id, rep_id="rep-1", contact_id=ana.id, channel="email", reason_label="x",
                ))
    asyncio.run(run())
    return company, ana, bia, opp


def _block(company_id, **body):
    payload = {"rep_id": "rep-1", "reason": "requested_by_contact", "comment": "Pediu por telefone", **body}
    return client.post(f"{BASE}/companies/{company_id}/do-not-contact", json=payload)


def test_create_list_and_lift_do_not_contact_keeps_history():
    with _TempDb() as db:
        company, ana, _, _ = _seed(db)
        created = _block(company.id, contact_id=ana.id, channel="E-mail")
        assert created.status_code == 200
        entry = created.json()
        assert entry["contact_email"] == "ana@aurora.com" and entry["channel"] == "email"
        lifted = client.post(f"{BASE}/do-not-contact/{entry['id']}/lift", json={"rep_id": "rep-2", "lift_reason": "Voltou a pedir proposta"})
        assert lifted.status_code == 200 and lifted.json()["lifted_by"] == "rep-2"
        listed = client.get(f"{BASE}/companies/{company.id}/do-not-contact").json()
        assert len(listed) == 1 and listed[0]["lifted_at"] is not None  # histórico mantido
        assert client.post(f"{BASE}/do-not-contact/inexistente/lift", json={"rep_id": "r"}).status_code == 404


def test_do_not_contact_rejects_contact_from_another_company():
    with _TempDb() as db:
        company, _, _, _ = _seed(db)
        resp = _block(company.id, contact_id="contato-de-outra-empresa")
        assert resp.status_code == 422


def test_contacts_list_flags_blocked_contact_by_email_even_with_other_casing():
    with _TempDb() as db:
        company, ana, bia, _ = _seed(db)
        _block(company.id, contact_id=ana.id)
        flags = {c["name"]: c["do_not_contact"] for c in client.get(f"{BASE}/companies/{company.id}/contacts").json()}
        assert flags == {"Ana": True, "Bia": False}


def test_next_suggested_touch_is_blocked_when_whole_company_is_blocked():
    with _TempDb() as db:
        company, _, _, opp = _seed(db)
        _block(company.id)
        body = client.get(f"{BASE}/opportunities/{opp.id}/next-suggested-touch", params={"rep_id": "rep-1"}).json()
        assert body["state"] == "bloqueado"
        assert body["block_reason"] and "comment" not in body and "Pediu por telefone" not in str(body)
        assert body["silence_reason"] is None and body["threading_risk_reasons"] == []


def test_next_suggested_touch_flags_blocked_last_contact_without_blocking_suggestion():
    with _TempDb() as db:
        company, ana, _, opp = _seed(db, with_touch=True)
        _block(company.id, contact_id=ana.id)
        body = client.get(f"{BASE}/opportunities/{opp.id}/next-suggested-touch", params={"rep_id": "rep-1"}).json()
        assert body["state"] != "bloqueado" and body["last_contact_blocked"] is True


def test_outreach_touch_requires_acknowledgement_when_target_is_blocked():
    with _TempDb() as db:
        company, ana, bia, opp = _seed(db)
        _block(company.id, contact_id=ana.id)
        url = f"{BASE}/opportunities/{opp.id}/outreach-touches"
        payload = {"rep_id": "rep-1", "contact_id": ana.id, "channel": "email", "reason_label": "Retomada"}
        refused = client.post(url, json=payload)
        assert refused.status_code == 422 and "não contatar" in refused.json()["detail"]
        assert "Pediu por telefone" not in refused.json()["detail"]
        assert client.post(url, json={**payload, "contact_id": bia.id}).json()["block_acknowledged"] is False
        confirmed = client.post(url, json={**payload, "acknowledge_block": True})
        assert confirmed.status_code == 200 and confirmed.json()["block_acknowledged"] is True


def test_outreach_touch_rejects_contact_that_does_not_belong_to_the_company():
    with _TempDb() as db:
        _, _, _, opp = _seed(db)
        resp = client.post(
            f"{BASE}/opportunities/{opp.id}/outreach-touches",
            json={"rep_id": "rep-1", "contact_id": "inventado", "channel": "email", "reason_label": "x"},
        )
        assert resp.status_code == 422


def test_email_draft_is_refused_for_blocked_target_without_calling_ai(monkeypatch):
    with _TempDb() as db:
        company, ana, _, opp = _seed(db)
        _block(company.id, contact_id=ana.id, channel="email")
        monkeypatch.setattr(routes_exports, "session_factory", db.session_factory)
        monkeypatch.setattr(routes_exports, "load_env", lambda path: {"AI_API_KEY": "chave-falsa", "AI_PROVIDER": "claude"})

        def _must_not_run(*args, **kwargs):
            raise AssertionError("IA não pode ser chamada para alvo bloqueado")

        monkeypatch.setattr(routes_exports, "create_ai_provider", _must_not_run)
        resp = client.post(f"{BASE}/email-draft", json={
            "opportunity_id": opp.id, "contact_id": ana.id, "company_name": "Aurora", "opportunity_type": "cross-sell",
        })
        assert resp.status_code == 422 and "não contatar" in resp.json()["detail"]


def test_draft_and_touch_without_contact_are_refused_when_a_contact_of_the_company_is_blocked(monkeypatch):
    with _TempDb() as db:
        company, ana, _, opp = _seed(db)
        _block(company.id, contact_id=ana.id)
        monkeypatch.setattr(routes_exports, "session_factory", db.session_factory)
        monkeypatch.setattr(routes_exports, "load_env", lambda path: {"AI_API_KEY": "chave-falsa", "AI_PROVIDER": "claude"})
        monkeypatch.setattr(routes_exports, "create_ai_provider", lambda *a, **k: (_ for _ in ()).throw(AssertionError("IA chamada")))
        draft = client.post(f"{BASE}/email-draft", json={"opportunity_id": opp.id, "company_name": "Aurora", "opportunity_type": "cross-sell"})
        assert draft.status_code == 422 and "escolha para qual contato" in draft.json()["detail"]
        touch = client.post(
            f"{BASE}/opportunities/{opp.id}/outreach-touches",
            json={"rep_id": "rep-1", "channel": "email", "reason_label": "x"},
        )
        assert touch.status_code == 422 and "escolha para qual contato" in touch.json()["detail"]
        ok_other_channel = client.post(
            f"{BASE}/opportunities/{opp.id}/outreach-touches",
            json={"rep_id": "rep-1", "channel": "linkedin", "reason_label": "x", "acknowledge_block": True},
        )
        assert ok_other_channel.status_code == 200


def test_block_created_with_hyphenated_channel_still_blocks_plain_email_touch():
    with _TempDb() as db:
        company, ana, _, opp = _seed(db)
        _block(company.id, contact_id=ana.id, channel="E-mail")
        resp = client.post(
            f"{BASE}/opportunities/{opp.id}/outreach-touches",
            json={"rep_id": "rep-1", "contact_id": ana.id, "channel": "email", "reason_label": "x"},
        )
        assert resp.status_code == 422
