"""Fase Q — rota de enriquecimento (API mockada, só empresas fictícias, banco/.env temporários)."""
import asyncio
import logging
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import routes_enrichment  # noqa: E402
from core.models import Company  # noqa: E402
from core.repository import list_companies, list_field_conflicts, save_company  # noqa: E402
from providers.enrichment_http import EnrichmentHttpProvider  # noqa: E402
from tests.test_routes_sync import _TempDb, client  # noqa: E402

BASE = "/modules/lead_tracker"
KEY = "chave-super-secreta-123"
JSON = {"content-type": "application/json"}
CONFIG = {
    "ENRICHMENT_ENABLED": "true", "ENRICHMENT_URL_TEMPLATE": "https://api.exemplo.com/v1/companies?domain={domain}",
    "ENRICHMENT_AUTH_HEADER": "X-Api-Key", "ENRICHMENT_API_KEY": KEY,
    "ENRICHMENT_MAP_EMPLOYEES": "metrics.employees", "ENRICHMENT_MAP_INDUSTRY": "category.industry",
}


def _env(db, **overrides):
    values = {"APP_ENV": "local", **CONFIG, **overrides}
    db.env_path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8")


def _patch_api(monkeypatch, handler):
    calls: list[httpx.Request] = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    async def resolver(host, port):
        return ["93.184.216.34"]

    def from_env(env):
        client_ = httpx.AsyncClient(transport=httpx.MockTransport(wrapped), follow_redirects=False)
        return EnrichmentHttpProvider(
            env["ENRICHMENT_URL_TEMPLATE"], env["ENRICHMENT_AUTH_HEADER"], env["ENRICHMENT_API_KEY"],
            env["ENRICHMENT_MAP_EMPLOYEES"], env["ENRICHMENT_MAP_INDUSTRY"], client=client_, resolver=resolver, retry_wait=0,
        )

    monkeypatch.setattr(routes_enrichment.EnrichmentHttpProvider, "from_env", staticmethod(from_env))
    return calls


def _seed(db, *companies):
    async def go():
        async with db.session_factory() as session:
            for company in companies:
                await save_company(session, company)
    asyncio.run(go())


def _state(db):
    async def go():
        async with db.session_factory() as session:
            return {c.name: c for c in await list_companies(session)}, await list_field_conflicts(session)
    return asyncio.run(go())


def _answer(domains: dict[str, dict]):
    def handler(request):
        body = domains.get(request.url.params["domain"])
        return httpx.Response(404, headers=JSON, json={}) if body is None else httpx.Response(200, headers=JSON, json=body)
    return handler


def _run(monkeypatch, db, handler, **params):
    _patch_api(monkeypatch, handler)
    monkeypatch.setattr(routes_enrichment, "session_factory", db.session_factory)
    return client.post(f"{BASE}/enrichment/run", params=params)


def test_fills_empty_fields_with_enrichment_origin_and_counts_no_data(monkeypatch):
    with _TempDb() as db:
        _env(db)
        _seed(db, Company(name="Acme Teste", website="https://acme-teste.com.br"),
              Company(name="Beta Teste", website="https://beta-teste.com.br"))
        resp = _run(monkeypatch, db, _answer({"acme-teste.com.br": {"metrics": {"employees": "120"}, "category": {"industry": "Varejo"}}}))
        assert resp.status_code == 200
        assert resp.json() == {"enriquecidas": 1, "sem_dado": 1, "conflitos": 0, "erros": []}
        companies, conflicts = _state(db)
        acme = companies["Acme Teste"]
        assert acme.industry == "Varejo" and acme.employee_count == 120
        assert acme.field_sources["industry"] == "enrichment" and acme.field_sources["employee_count"] == "enrichment"
        assert companies["Beta Teste"].industry is None and conflicts == []


def test_value_from_crm_is_kept_and_opens_a_conflict_while_empty_field_is_filled(monkeypatch):
    with _TempDb() as db:
        _env(db)
        _seed(db, Company(name="Acme Teste", website="https://acme-teste.com.br", industry="Software",
                          field_sources={"industry": "salesforce"}))
        resp = _run(monkeypatch, db, _answer({"acme-teste.com.br": {"metrics": {"employees": 30}, "category": {"industry": "Varejo"}}}))
        assert resp.json() == {"enriquecidas": 1, "sem_dado": 0, "conflitos": 1, "erros": []}
        companies, conflicts = _state(db)
        assert companies["Acme Teste"].industry == "Software" and companies["Acme Teste"].employee_count == 30
        assert len(conflicts) == 1 and conflicts[0].field == "industry"
        assert {c.source for c in conflicts[0].candidates} == {"salesforce", "enrichment"}
        again = _run(monkeypatch, db, _answer({"acme-teste.com.br": {"category": {"industry": "Varejo"}}}))
        assert len(_state(db)[1]) == 1  # não duplica o conflito aberto
        assert again.status_code == 200


def test_mapping_origin_is_never_contested_and_range_is_not_filled(monkeypatch):
    with _TempDb() as db:
        _env(db)
        _seed(db, Company(name="Acme Teste", website="https://acme-teste.com.br", industry="Escolha do usuário",
                          field_sources={"industry": "mapping"}))
        resp = _run(monkeypatch, db, _answer({"acme-teste.com.br": {"metrics": {"employees": "51-200"}, "category": {"industry": "Varejo"}}}))
        assert resp.json() == {"enriquecidas": 0, "sem_dado": 1, "conflitos": 0, "erros": []}
        companies, conflicts = _state(db)
        assert companies["Acme Teste"].industry == "Escolha do usuário" and companies["Acme Teste"].employee_count is None
        assert conflicts == []


def test_only_companies_with_valid_own_website_and_empty_field_are_called(monkeypatch):
    with _TempDb() as db:
        _env(db)
        _seed(db, Company(name="Sem site"), Company(name="Rede social", website="https://www.facebook.com/acme"),
              Company(name="Completa", website="https://completa.com.br", industry="X", employee_count=5),
              Company(name="Falta porte", website="https://faltaporte.com.br", industry="X"))
        _patch_api(monkeypatch, _answer({"faltaporte.com.br": {"metrics": {"employees": 9}}}))
        calls = []
        original = routes_enrichment.EnrichmentHttpProvider.from_env

        def spy(env):
            provider = original(env)
            real = provider.enrich

            async def enrich(site):
                calls.append(site)
                return await real(site)
            provider.enrich = enrich
            return provider

        monkeypatch.setattr(routes_enrichment.EnrichmentHttpProvider, "from_env", staticmethod(spy))
        monkeypatch.setattr(routes_enrichment, "session_factory", db.session_factory)
        resp = client.post(f"{BASE}/enrichment/run")
        assert resp.json()["enriquecidas"] == 1 and calls == ["https://faltaporte.com.br"]


def test_limit_is_validated_and_applied(monkeypatch):
    with _TempDb() as db:
        _env(db)
        _seed(db, *[Company(name=f"Empresa {i:02d}", website=f"https://empresa{i:02d}.com.br") for i in range(5)])
        for bad in (0, 201, -1):
            assert client.post(f"{BASE}/enrichment/run", params={"limit": bad}).status_code == 422
        calls = _patch_api(monkeypatch, _answer({}))
        monkeypatch.setattr(routes_enrichment, "session_factory", db.session_factory)
        assert client.post(f"{BASE}/enrichment/run", params={"limit": 2}).json()["sem_dado"] == 2 and len(calls) == 2


def test_401_stops_the_batch_with_friendly_message_and_no_key(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    with _TempDb() as db:
        _env(db)
        _seed(db, *[Company(name=f"Empresa {i}", website=f"https://empresa{i}.com.br") for i in range(4)])
        calls = _patch_api(monkeypatch, lambda r: httpx.Response(401, headers=JSON, json={}))
        monkeypatch.setattr(routes_enrichment, "session_factory", db.session_factory)
        resp = client.post(f"{BASE}/enrichment/run")
        body = resp.json()
        assert resp.status_code == 200 and len(calls) == 1 and len(body["erros"]) == 1 and "chave" in body["erros"][0]
        assert KEY not in resp.text and KEY not in caplog.text


def test_429_retries_once_then_skips_company_and_continues(monkeypatch):
    with _TempDb() as db:
        _env(db)
        _seed(db, Company(name="Alfa", website="https://alfa.com.br"), Company(name="Beta", website="https://beta.com.br"))

        def handler(request):
            if request.url.params["domain"] == "alfa.com.br":
                return httpx.Response(429, headers=JSON, json={})
            return httpx.Response(200, headers=JSON, json={"metrics": {"employees": 8}})
        calls = _patch_api(monkeypatch, handler)
        monkeypatch.setattr(routes_enrichment, "session_factory", db.session_factory)
        body = client.post(f"{BASE}/enrichment/run").json()
        assert body["enriquecidas"] == 1 and len(body["erros"]) == 1 and body["erros"][0].startswith("Alfa:")
        assert [c.url.params["domain"] for c in calls].count("alfa.com.br") == 2


def test_timeout_becomes_friendly_error_in_the_response(monkeypatch):
    with _TempDb() as db:
        _env(db)
        _seed(db, Company(name="Alfa", website="https://alfa.com.br"))

        def handler(request):
            raise httpx.ReadTimeout("lento", request=request)
        body = _run(monkeypatch, db, handler).json()
        assert body["enriquecidas"] == 0 and "não respondeu" in body["erros"][0] and "Timeout" not in body["erros"][0]


def test_disabled_or_incomplete_source_is_an_actionable_domain_error(monkeypatch):
    with _TempDb() as db:
        monkeypatch.setattr(routes_enrichment, "session_factory", db.session_factory)
        _env(db, ENRICHMENT_ENABLED="false")
        resp = client.post(f"{BASE}/enrichment/run")
        assert resp.status_code == 503 and "desligado" in resp.json()["detail"]
        _env(db, ENRICHMENT_URL_TEMPLATE="")
        resp = client.post(f"{BASE}/enrichment/run")
        assert resp.status_code == 503 and "Informe" in resp.json()["detail"]


def test_settings_never_return_the_key_and_connection_test_shows_values(monkeypatch):
    with _TempDb() as db:
        _env(db)
        listing = client.get(f"{BASE}/settings")
        assert KEY not in listing.text
        source = next(s for s in listing.json() if s["id"] == "enrichment")
        assert next(f for f in source["fields"] if f["key"] == "ENRICHMENT_API_KEY")["has_value"] is True
        _patch_api(monkeypatch, lambda r: httpx.Response(200, headers=JSON, json={"metrics": {"employees": 42}, "category": {"industry": "Varejo"}}))
        test = client.post(f"{BASE}/settings/enrichment/test")
        assert test.json()["status"] == "connected" and "Varejo" in test.json()["message"] and KEY not in test.text


def test_run_is_refused_while_another_update_holds_the_lock(monkeypatch):
    import asyncio
    from backend.sync import SYNC_LOCK
    with _TempDb() as db:
        _env(db)
        _seed(db, Company(name="Acme Teste", website="https://acme-teste.com.br"))

        async def held():
            async with SYNC_LOCK:
                return _run(monkeypatch, db, _answer({}))
        resp = asyncio.run(held())
        assert resp.status_code >= 400 and "em andamento" in resp.text
