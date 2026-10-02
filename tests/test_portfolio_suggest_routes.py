"""Fase P — rotas de sugestão de portfólio a partir do site (coleta e IA falsas, sem rede)."""
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.base import AIProvider, AIResponse  # noqa: E402
from backend import routes_portfolio_suggest  # noqa: E402
from core.models import Product, Service, Vendor  # noqa: E402
from core.repository import list_products, list_services, list_vendors, save_product, save_service, save_vendor  # noqa: E402
from providers.base import ConnectionTestResult  # noqa: E402
from providers.website import WebsiteProvider  # noqa: E402
from tests.test_routes_sync import _TempDb, client  # noqa: E402

BASE = "/modules/lead_tracker"
URL = "https://acme.com.br/"
TEXT = "Somos parceiros Veeam e revendemos o Veeam Backup & Replication. Oferecemos Consultoria em Nuvem para empresas."


class _FakeAI(AIProvider):
    def __init__(self, items):
        self._items = items

    @property
    def id(self):
        return "fake"

    async def test_connection(self):
        return ConnectionTestResult.ok()

    async def generate(self, request):
        return AIResponse(content="", structured={"itens": self._items})


def _env(db, **values):
    lines = ["APP_ENV=local"] + [f"{k}={v}" for k, v in values.items()]
    db.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_site(monkeypatch, ai_items):
    async def resolver(host, port):
        return ["93.184.216.34"]

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404, headers={"content-type": "text/plain"}, text="")
        return httpx.Response(200, headers={"content-type": "text/html"}, text=f"<p>{TEXT}</p>")

    transport = httpx.MockTransport(handler)
    original = routes_portfolio_suggest.WebsiteProvider

    def build(site_url):
        return original(site_url, client=httpx.AsyncClient(transport=transport, follow_redirects=False), resolver=resolver)

    monkeypatch.setattr(routes_portfolio_suggest, "WebsiteProvider", build)
    monkeypatch.setattr(routes_portfolio_suggest, "create_ai_provider", lambda *a, **k: _FakeAI(ai_items))


def _item(**kw):
    base = {"tipo": "produto", "nome": "Veeam Backup & Replication", "fabricante": "Veeam",
            "evidencia": "revendemos o Veeam Backup & Replication", "pagina": URL}
    base.update(kw)
    return base


def test_without_ai_key_the_route_explains_and_never_reads_the_site(monkeypatch):
    with _TempDb() as db:
        _env(db, COMPANY_WEBSITE="https://acme.com.br")
        monkeypatch.setattr(routes_portfolio_suggest, "WebsiteProvider", lambda url: (_ for _ in ()).throw(AssertionError("site lido")))
        resp = client.post(f"{BASE}/portfolio-suggestions")
        assert resp.status_code in (400, 422, 503) and "IA" in resp.json()["detail"]


def test_without_or_with_internal_site_url_it_is_a_friendly_error(monkeypatch):
    with _TempDb() as db:
        for site in ("", "http://127.0.0.1:8000", "http://localhost"):
            _env(db, AI_API_KEY="chave-falsa", COMPANY_WEBSITE=site)
            resp = client.post(f"{BASE}/portfolio-suggestions")
            assert resp.status_code >= 400 and "127.0.0.1" not in resp.json()["detail"]


def test_suggestions_are_validated_flag_duplicates_and_nothing_is_saved(monkeypatch):
    with _TempDb() as db:
        monkeypatch.setattr(routes_portfolio_suggest, "session_factory", db.session_factory)
        _env(db, AI_API_KEY="chave-falsa", COMPANY_WEBSITE="https://acme.com.br")
        _patch_site(monkeypatch, [_item(), _item(nome="Produto Inventado XYZ"),
                                  {"tipo": "servico", "nome": "Consultoria em Nuvem", "fabricante": None,
                                   "evidencia": "Oferecemos Consultoria em Nuvem para empresas", "pagina": URL}])

        async def seed():
            async with db.session_factory() as session:
                await save_service(session, Service(name="consultoria em nuvem"))
        asyncio.run(seed())
        body = client.post(f"{BASE}/portfolio-suggestions").json()
        assert body["pages_read"] == 1 and body["discarded"] == 1
        by_name = {s["name"]: s for s in body["suggestions"]}
        assert by_name["Veeam Backup & Replication"]["already_in_catalog"] is False
        assert by_name["Consultoria em Nuvem"]["already_in_catalog"] is True  # comparação ignora caixa

        async def counts():
            async with db.session_factory() as session:
                return len(await list_vendors(session)), len(await list_products(session))
        assert asyncio.run(counts()) == (0, 0)  # sugerir NUNCA grava


def test_apply_creates_only_marked_items_reuses_vendor_and_skips_existing(monkeypatch):
    with _TempDb() as db:
        monkeypatch.setattr(routes_portfolio_suggest, "session_factory", db.session_factory)
        async def seed():
            async with db.session_factory() as session:
                vendor = Vendor(name="Veeam")
                await save_vendor(session, vendor)
                await save_product(session, Product(vendor_id=vendor.id, name="Veeam One", aliases=["VeeamONE"]))
        asyncio.run(seed())
        resp = client.post(f"{BASE}/portfolio-suggestions/apply", json={"items": [
            {"kind": "product", "name": "Veeam Backup & Replication", "vendor_name": "veeam"},
            {"kind": "product", "name": "veeamone", "vendor_name": "Veeam"},          # alias já existe
            {"kind": "product", "name": "Produto Novo", "vendor_name": "Fabricante Novo"},
            {"kind": "service", "name": "Consultoria em Nuvem"},
            {"kind": "vendor", "name": "VEEAM"},                                       # fabricante já existe
        ]})
        assert resp.status_code == 200
        assert resp.json() == {"created": {"vendor": 1, "product": 2, "service": 1}, "skipped_existing": 2}

        async def state():
            async with db.session_factory() as session:
                return [v.name for v in await list_vendors(session)], len(await list_products(session))
        vendors, products = asyncio.run(state())
        assert sorted(vendors) == ["Fabricante Novo", "Veeam"] and products == 3
        again = client.post(f"{BASE}/portfolio-suggestions/apply", json={"items": [{"kind": "service", "name": "consultoria em nuvem"}]})
        assert again.json()["created"]["service"] == 0 and again.json()["skipped_existing"] == 1


def test_apply_rejects_markup_product_without_vendor_and_too_many_items():
    with _TempDb():
        url = f"{BASE}/portfolio-suggestions/apply"
        assert client.post(url, json={"items": [{"kind": "service", "name": "<script>alert(1)</script>"}]}).status_code == 422
        assert client.post(url, json={"items": [{"kind": "service", "name": "https://evil.com/x"}]}).status_code == 422
        assert client.post(url, json={"items": [{"kind": "product", "name": "Produto Sem Fabricante"}]}).status_code == 422
        assert client.post(url, json={"items": []}).status_code == 422
        many = [{"kind": "service", "name": f"Servico {i:03d}"} for i in range(51)]
        assert client.post(url, json={"items": many}).status_code == 422
