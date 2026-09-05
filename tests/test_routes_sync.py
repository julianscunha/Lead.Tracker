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
from core.models import Company, Opportunity, OpportunityStatus, Product, Service, SourceRef
from core.repository import save_company, save_opportunity, save_product, save_service

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


def test_get_opportunities_includes_risk_flag():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas")
        opportunity = Opportunity(
            company_id=company.id, type="risk", risk_flag="vdc365 sem assessment.",
            sources=[SourceRef(type="rule_engine")],
        )

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
        asyncio.run(seed())

        resp = client.get("/modules/lead_tracker/opportunities")
        assert resp.json()[0]["risk_flag"] == "vdc365 sem assessment."


def test_get_opportunities_includes_severity_band_not_avaliado_by_default():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas")
        opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
        asyncio.run(seed())

        resp = client.get("/modules/lead_tracker/opportunities")
        body = resp.json()[0]
        assert body["severity_band"] == "nao_avaliado"
        assert body["scope_note"] is None
        assert body["criticality"] is None


def test_patch_opportunity_qualification_updates_and_recomputes_severity_band():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas")
        opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
        asyncio.run(seed())

        resp = client.patch(
            f"/modules/lead_tracker/opportunities/{opportunity.id}",
            json={"scope_note": "generalizado", "criticality": "critico_exposto", "severity_note": "Afeta todos os sites."},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["scope_note"] == "generalizado"
        assert body["criticality"] == "critico_exposto"
        assert body["severity_note"] == "Afeta todos os sites."
        assert body["severity_band"] == "critico"


def test_patch_opportunity_qualification_returns_friendly_404_for_unknown_id():
    with _TempDb():
        resp = client.patch(
            "/modules/lead_tracker/opportunities/id-inexistente",
            json={"scope_note": "isolado", "criticality": "nao_critico"},
        )
        assert resp.status_code == 404
        assert "não encontrada" in resp.json()["detail"]


def test_patch_opportunity_qualification_rejects_value_outside_the_three_options():
    """Fronteira HTTP: scope_note/criticality ficam string aberta no domínio
    (core/models.py), mas a rota PATCH é acessível por qualquer cliente, não
    só a UI com dropdown — um valor fora das 3 opções deve ser rejeitado
    aqui, não silenciosamente virar 'não avaliado' em compute_severity_band."""
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas")
        opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
        asyncio.run(seed())

        resp = client.patch(
            f"/modules/lead_tracker/opportunities/{opportunity.id}",
            json={"scope_note": "todo-o-parque-inteiro", "criticality": "nao_critico"},
        )
        assert resp.status_code == 422


def test_get_products_and_services_return_catalog():
    with _TempDb() as db:
        import asyncio
        product = Product(id="veeam_vbr", vendor_id="v1", name="Veeam VBR", category="backup")
        service = Service(id="zabbix", name="Zabbix", category="monitoring")

        async def seed():
            async with db.session_factory() as session:
                await save_product(session, product)
                await save_service(session, service)
        asyncio.run(seed())

        products_resp = client.get("/modules/lead_tracker/products")
        services_resp = client.get("/modules/lead_tracker/services")
        assert products_resp.json()[0]["category"] == "backup"
        assert services_resp.json()[0]["category"] == "monitoring"


def test_post_rule_creates_and_get_rules_lists_it():
    with _TempDb():
        body = {
            "opportunity_type": "cross-sell", "justification": "Tem backup, sem monitoramento.",
            "requires_category": ["backup"], "absent_category": ["monitoring"],
        }
        create_resp = client.post("/modules/lead_tracker/rules", json=body)
        assert create_resp.status_code == 200
        assert create_resp.json()["active"] is True

        list_resp = client.get("/modules/lead_tracker/rules")
        assert len(list_resp.json()) == 1
        assert list_resp.json()[0]["requires_category"] == ["backup"]


def test_post_rule_without_any_evidence_mechanism_returns_friendly_error():
    with _TempDb():
        body = {"opportunity_type": "cross-sell", "justification": "sem evidência nenhuma"}
        resp = client.post("/modules/lead_tracker/rules", json=body)
        assert resp.status_code == 422
        assert "evidência" in resp.json()["detail"]


if __name__ == "__main__":
    test_get_companies_returns_empty_list_on_fresh_install()
    test_get_companies_returns_persisted_company()
    test_get_opportunities_embeds_company_name()
    test_get_opportunities_empty_on_fresh_install_never_fake_data()
    test_get_dashboard_metrics_reflects_empty_state_honestly()
    test_sync_endpoint_with_no_source_enabled_returns_empty_list()
    test_sync_endpoint_reads_isolated_env_never_the_real_module_env()
    test_get_opportunities_includes_risk_flag()
    test_get_opportunities_includes_severity_band_not_avaliado_by_default()
    test_patch_opportunity_qualification_updates_and_recomputes_severity_band()
    test_patch_opportunity_qualification_returns_friendly_404_for_unknown_id()
    test_patch_opportunity_qualification_rejects_value_outside_the_three_options()
    test_get_products_and_services_return_catalog()
    test_post_rule_creates_and_get_rules_lists_it()
    test_post_rule_without_any_evidence_mechanism_returns_friendly_error()
    print("OK — todos os testes HTTP de dado real passaram")
