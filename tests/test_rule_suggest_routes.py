"""Rotas de sugestão de regras pela IA e checagem do catálogo em POST /rules (IA falsa, sem rede)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.base import AIProvider, AIProviderError, AIResponse  # noqa: E402
from backend import routes_rule_suggest  # noqa: E402
from core.errors import ErrorCategory  # noqa: E402
from core.models import Product, Service, Vendor  # noqa: E402
from core.repository import list_rules, save_product, save_service, save_vendor  # noqa: E402
from providers.base import ConnectionTestResult  # noqa: E402
from tests.test_routes_sync import _TempDb, client  # noqa: E402

BASE = "/modules/lead_tracker"


class _FakeAI(AIProvider):
    def __init__(self, structured=None, error=None):
        self._structured, self._error = structured, error

    @property
    def id(self):
        return "fake"

    async def test_connection(self):
        return ConnectionTestResult.ok()

    async def generate(self, request):
        if self._error:
            raise self._error
        return AIResponse(content="", structured=self._structured)


def _env(db, **values):
    db.env_path.write_text("\n".join(["APP_ENV=local"] + [f"{k}={v}" for k, v in values.items()]) + "\n", encoding="utf-8")


def _seed(db):
    async def go():
        async with db.session_factory() as session:
            await save_vendor(session, Vendor(id="v1", name="Fabrica Alfa"))
            await save_product(session, Product(id="p1", vendor_id="v1", name="Alfa Backup", category="Backup"))
            await save_service(session, Service(id="s1", name="Consultoria Beta", category="Consultoria"))
    asyncio.run(go())


def _setup(monkeypatch, db, structured=None, error=None):
    monkeypatch.setattr(routes_rule_suggest, "session_factory", db.session_factory)
    monkeypatch.setattr(routes_rule_suggest, "create_ai_provider", lambda *a, **k: _FakeAI(structured, error))
    _env(db, AI_API_KEY="chave-falsa")
    _seed(db)


RULE = {"tipo_oportunidade": "cross-sell", "justificativa": "Tem backup e falta consultoria.",
        "requer": ["p1"], "ausente": ["s1"], "requer_categoria": [], "ausente_categoria": [], "relacao": None}


def test_without_ai_key_the_route_explains_that_manual_rules_still_work():
    with _TempDb():
        resp = client.post(f"{BASE}/rule-suggestions")
        assert resp.status_code >= 400 and "IA" in resp.json()["detail"]


def test_ai_down_is_a_friendly_error(monkeypatch):
    with _TempDb() as db:
        _setup(monkeypatch, db, error=AIProviderError("falhou", category=ErrorCategory.AI, recommended_action="Tente depois."))
        resp = client.post(f"{BASE}/rule-suggestions")
        assert resp.status_code >= 400 and "Traceback" not in resp.text


def test_post_returns_labeled_cards_and_saves_nothing(monkeypatch):
    with _TempDb() as db:
        _setup(monkeypatch, db, {"regras": [RULE, {**RULE, "requer": ["inventado"]}]})
        body = client.post(f"{BASE}/rule-suggestions").json()
        assert body["discarded"] == 1 and len(body["suggestions"]) == 1
        card = body["suggestions"][0]
        assert card["requires_labels"] == ["Alfa Backup"] and card["absent_labels"] == ["Consultoria Beta"]
        assert "estimated_deal_value" not in card

        async def count():
            async with db.session_factory() as session:
                return len(await list_rules(session))
        assert asyncio.run(count()) == 0


def test_accepting_a_card_through_post_rules_creates_the_rule_with_optional_value(monkeypatch):
    with _TempDb() as db:
        _setup(monkeypatch, db, {"regras": [RULE]})
        card = client.post(f"{BASE}/rule-suggestions").json()["suggestions"][0]
        body = {k: card[k] for k in ("opportunity_type", "justification", "requires", "absent",
                                     "requires_category", "absent_category", "relation_type")}
        body["estimated_deal_value"] = 40000
        resp = client.post(f"{BASE}/rules", json=body)
        assert resp.status_code == 200 and resp.json()["estimated_deal_value"] == 40000
        assert len(client.get(f"{BASE}/rules").json()) == 1


def test_create_rule_rejects_unknown_ids_and_categories_when_catalog_exists():
    """Regressão: aceite adulterado (id/categoria inventados) não cria regra morta."""
    with _TempDb() as db:
        _seed(db)
        base = {"opportunity_type": "cross-sell", "justification": "Regra de teste válida."}
        assert client.post(f"{BASE}/rules", json={**base, "requires": ["inventado"]}).status_code == 422
        assert client.post(f"{BASE}/rules", json={**base, "requires": ["p1"], "absent": ["inventado"]}).status_code == 422
        assert client.post(f"{BASE}/rules", json={**base, "requires_category": ["Inventada"]}).status_code == 422
        ok = client.post(f"{BASE}/rules", json={**base, "requires_category": ["backup"]})
        assert ok.status_code == 200 and ok.json()["requires_category"] == ["Backup"]
        # "não tem categoria X" segue válido mesmo sem nada de X no catálogo (regressão do import CSV)
        assert client.post(f"{BASE}/rules", json={**base, "requires_category": ["Backup"], "absent_category": ["Outra"]}).status_code == 200
        assert client.post(f"{BASE}/rules", json={**base, "requires": ["v1"]}).status_code == 200
        assert len(client.get(f"{BASE}/rules").json()) == 3


def test_create_rule_with_empty_catalog_still_works_for_manual_use():
    with _TempDb():
        resp = client.post(f"{BASE}/rules", json={"opportunity_type": "x1", "justification": "Regra sem catálogo.",
                                                  "requires_category": ["backup"]})
        assert resp.status_code == 200
