"""Smoke tests HTTP das rotas de dado real (Fase B.1), via FastAPI
TestClient — banco SQLite temporário, nunca o banco real do módulo
(routes_sync.session_factory é redirecionado por teste, mesmo padrão de
tests/test_settings.py com _ENV_PATH)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / ".techforge-dev" / "sdk" / "python"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import main as backend_main
from backend import routes_settings, routes_sync
from core.db import create_engine, init_db, make_session_factory
from core.models import Company, Opportunity, OpportunityStatus, SourceRef
from core.repository import save_company, save_opportunity

app = FastAPI()
app.include_router(backend_main.router)
client = TestClient(app)


class _TempDb:
    """Redireciona routes_sync.session_factory (e routes_settings._ENV_PATH,
    já que /sync lê o .env pra saber quais fontes estão habilitadas) pra
    recursos temporários — nunca toca o banco/.env reais do checkout."""

    def __enter__(self):
        self._original_sf = routes_sync.session_factory
        self._original_env = routes_settings._ENV_PATH
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmpdir.name)

        import asyncio
        engine = create_engine(tmp_path / "test.db")
        asyncio.run(init_db(engine))
        self.session_factory = make_session_factory(engine)
        routes_sync.session_factory = self.session_factory

        env_path = tmp_path / ".env"
        env_path.write_text("APP_ENV=local\n", encoding="utf-8")
        routes_settings._ENV_PATH = env_path
        self.env_path = env_path
        return self

    def __exit__(self, *exc):
        routes_sync.session_factory = self._original_sf
        routes_settings._ENV_PATH = self._original_env
        self._tmpdir.cleanup()


def test_get_companies_returns_empty_list_on_fresh_install():
    with _TempDb():
        resp = client.get("/modules/lead_tracker/companies")
        assert resp.status_code == 200
        assert resp.json() == []


def test_get_companies_returns_persisted_company():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas", is_customer=True)

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
        asyncio.run(seed())

        resp = client.get("/modules/lead_tracker/companies")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "Aurora Sistemas"


def test_get_opportunities_embeds_company_name():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas", is_customer=True)
        opportunity = Opportunity(
            company_id=company.id, type="cross-sell", evidence=["veeam_vbr"],
            sources=[SourceRef(type="rule_engine")], status=OpportunityStatus.DETECTED,
        )

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
        asyncio.run(seed())

        resp = client.get("/modules/lead_tracker/opportunities")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["company_name"] == "Aurora Sistemas"
        assert body[0]["is_customer"] is True
        assert body[0]["status"] == "detected"


def test_get_opportunities_empty_on_fresh_install_never_fake_data():
    with _TempDb():
        resp = client.get("/modules/lead_tracker/opportunities")
        assert resp.status_code == 200
        assert resp.json() == []


def test_get_dashboard_metrics_reflects_empty_state_honestly():
    with _TempDb():
        resp = client.get("/modules/lead_tracker/dashboard-metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["kpis"]["opportunities_identified"] == 0
        assert body["kpis"]["top_vendor"] is None


def test_sync_endpoint_with_no_source_enabled_returns_empty_list():
    with _TempDb():
        resp = client.post("/modules/lead_tracker/sync")
        assert resp.status_code == 200
        assert resp.json() == []


def test_sync_endpoint_reads_isolated_env_never_the_real_module_env():
    """Regressão: routes_sync.py chegou a ter seu próprio _ENV_PATH,
    duplicado do de routes_settings.py, nunca redirecionado pelo _TempDb —
    em um install real com SALESFORCE_ENABLED=true e credencial de verdade
    no .env real, rodar este teste teria disparado uma chamada de rede real
    ao Salesforce. Prova que a rota lê exatamente o .env temporário: liga
    Salesforce no .env isolado (sem credencial) e espera erro de config
    incompleta — nunca timeout de rede real, nunca sucesso inesperado."""
    with _TempDb() as db:
        db.env_path.write_text(db.env_path.read_text() + "SALESFORCE_ENABLED=true\n", encoding="utf-8")

        resp = client.post("/modules/lead_tracker/sync")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["source_id"] == "salesforce"
        assert body[0]["errors"] != []
        assert "incompleta" in body[0]["errors"][0]


if __name__ == "__main__":
    test_get_companies_returns_empty_list_on_fresh_install()
    test_get_companies_returns_persisted_company()
    test_get_opportunities_embeds_company_name()
    test_get_opportunities_empty_on_fresh_install_never_fake_data()
    test_get_dashboard_metrics_reflects_empty_state_honestly()
    test_sync_endpoint_with_no_source_enabled_returns_empty_list()
    test_sync_endpoint_reads_isolated_env_never_the_real_module_env()
    print("OK — todos os testes HTTP de dado real passaram")
