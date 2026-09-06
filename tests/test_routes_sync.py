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
from core.repository import (
    recompute_daily_snapshot, save_company, save_opportunity, save_product, save_service,
    update_company_renewal_date,
)

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
        assert body["funnel_reach"] == [
            {"stage": s, "reach_count": 0, "reach_ratio_from_previous": None}
            for s in ["detected", "qualified", "reviewed", "contacted", "opportunity"]
        ]
        assert body["weighted_potential"] == {
            "gross_total": 0.0, "weighted_evaluated_total": 0.0, "weighted_estimated_total": 0.0,
        }
        assert body["zombie_count"] == 0
        assert body["aging_count"] == 0
        assert body["aging_sla_days"] == 7


def test_get_dashboard_metrics_reads_snapshot_and_excludes_zombie_from_weighted_potential():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas", rep_id="rep-1", segment="enterprise")
        healthy = Opportunity(
            company_id=company.id, type="cross-sell", financial_potential=1000.0, confidence_score=0.8,
            sources=[SourceRef(type="salesforce")],
        )
        zombie = Opportunity(
            company_id=company.id, type="service", financial_potential=5000.0, confidence_score=0.9,
            sources=[SourceRef(type="salesforce")], first_detected_at="2020-01-01T00:00:00+00:00",
        )

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, healthy)
                await save_opportunity(session, zombie)
                await recompute_daily_snapshot(session)
        asyncio.run(seed())

        body = client.get("/modules/lead_tracker/dashboard-metrics").json()
        assert body["zombie_count"] == 1
        # zumbi (financial_potential=5000) nunca entra no ponderado nem nos cortes
        assert body["weighted_potential"]["gross_total"] == 1000.0
        assert body["potential_by_rep"] == [["rep-1", 1000.0]]
        # a "zumbi" também está em detected desde 2020 -> conta como aging (SLA padrão 7 dias)
        assert body["aging_count"] == 1
        assert body["aging_sla_days"] == 7


def test_dashboard_metrics_rep_without_target_shows_no_coverage_ratio():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas", rep_id="rep-1", segment="enterprise")
        opportunity = Opportunity(
            company_id=company.id, type="cross-sell", financial_potential=1000.0,
            sources=[SourceRef(type="salesforce")],
        )

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await recompute_daily_snapshot(session)
        asyncio.run(seed())

        body = client.get("/modules/lead_tracker/dashboard-metrics").json()
        coverage = {c["rep_id"]: c for c in body["rep_coverage"]}
        assert coverage["rep-1"]["actual"] == 1000.0
        assert coverage["rep-1"]["target"] is None
        assert coverage["rep-1"]["coverage_ratio"] is None  # nunca 0%, sem meta cadastrada


def test_dashboard_metrics_reads_coverage_from_configured_rep_target():
    with _TempDb() as db:
        import asyncio
        from datetime import date
        from core.opportunity_engine import current_period_key
        from core.models import PeriodType

        company = Company(name="Aurora Sistemas", rep_id="rep-1", segment="enterprise")
        opportunity = Opportunity(
            company_id=company.id, type="cross-sell", financial_potential=5000.0,
            sources=[SourceRef(type="salesforce")],
        )
        current_month = current_period_key(PeriodType.MONTHLY, date.today())

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await recompute_daily_snapshot(session)
        asyncio.run(seed())

        client.post("/modules/lead_tracker/rep-targets", json={
            "rep_id": "rep-1", "period_type": "monthly", "period_key": current_month, "target_amount": 10000.0,
        })

        body = client.get("/modules/lead_tracker/dashboard-metrics").json()
        coverage = {c["rep_id"]: c for c in body["rep_coverage"]}
        assert coverage["rep-1"]["target"] == 10000.0
        assert coverage["rep-1"]["coverage_ratio"] == 0.5
        assert body["coverage_period_type"] == "monthly"
        assert body["coverage_period_key"] == current_month


def test_post_rep_target_same_rep_period_upserts():
    with _TempDb():
        resp1 = client.post("/modules/lead_tracker/rep-targets", json={
            "rep_id": "rep-1", "period_type": "monthly", "period_key": "2026-09", "target_amount": 50000.0,
        })
        assert resp1.status_code == 200
        resp2 = client.post("/modules/lead_tracker/rep-targets", json={
            "rep_id": "rep-1", "period_type": "monthly", "period_key": "2026-09", "target_amount": 75000.0,
        })
        assert resp2.status_code == 200

        listed = client.get(
            "/modules/lead_tracker/rep-targets", params={"period_type": "monthly", "period_key": "2026-09"},
        ).json()
        assert len(listed) == 1
        assert listed[0]["target_amount"] == 75000.0


def test_get_icp_profile_before_any_save_returns_all_none_never_404():
    with _TempDb():
        resp = client.get("/modules/lead_tracker/icp-profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "reference_product_id": None, "place_category": None, "company_size_hint": None, "radius_km": None,
            "search_origin_address": None,
        }


def test_put_icp_profile_round_trips_and_upserts():
    with _TempDb():
        resp = client.put("/modules/lead_tracker/icp-profile", json={
            "reference_product_id": "p1", "place_category": "car_dealer", "company_size_hint": "media",
            "radius_km": 25.0, "search_origin_address": "Av. Paulista, São Paulo",
        })
        assert resp.status_code == 200
        assert resp.json()["place_category"] == "car_dealer"
        assert resp.json()["search_origin_address"] == "Av. Paulista, São Paulo"

        resp2 = client.put("/modules/lead_tracker/icp-profile", json={"place_category": "restaurant", "radius_km": 10.0})
        assert resp2.status_code == 200
        assert resp2.json()["place_category"] == "restaurant"

        loaded = client.get("/modules/lead_tracker/icp-profile").json()
        assert loaded["place_category"] == "restaurant"
        assert loaded["radius_km"] == 10.0


def test_put_icp_profile_rejects_negative_radius():
    with _TempDb():
        resp = client.put("/modules/lead_tracker/icp-profile", json={"radius_km": -5.0})
        assert resp.status_code == 422


def test_get_icp_suggestion_returns_null_without_any_satisfied_customer():
    with _TempDb():
        resp = client.get("/modules/lead_tracker/icp-suggestion")
        assert resp.status_code == 200
        assert resp.json() is None


def test_get_icp_suggestion_reflects_satisfied_customers():
    with _TempDb() as db:
        import asyncio
        companies = [Company(name=f"Cliente {i}", is_customer=True, industry="Varejo") for i in range(5)]
        opportunities = [
            Opportunity(company_id=c.id, type="cross-sell", opportunity_score=0.9) for c in companies
        ]

        async def seed():
            async with db.session_factory() as session:
                for c in companies:
                    await save_company(session, c)
                for o in opportunities:
                    await save_opportunity(session, o)
        asyncio.run(seed())

        resp = client.get("/modules/lead_tracker/icp-suggestion")
        assert resp.status_code == 200
        body = resp.json()
        assert body["industry_hint"] == "Varejo"
        assert body["industry_hint_share"] == 1.0
        assert body["sample_size"] == 5
        assert body["confidence"] == "high"


def test_post_rep_target_rejects_period_key_that_does_not_match_period_type():
    """Achado da revisão de código: sem essa validação, um typo no
    period_key nunca casa com `current_period_key()` — a meta cadastrada
    fica "órfã" e some silenciosamente pro dashboard, sem nenhum aviso."""
    with _TempDb():
        resp = client.post("/modules/lead_tracker/rep-targets", json={
            "rep_id": "rep-1", "period_type": "monthly", "period_key": "2026-Q3", "target_amount": 1000.0,
        })
        assert resp.status_code == 422


def test_post_rep_target_rejects_negative_amount():
    with _TempDb():
        resp = client.post("/modules/lead_tracker/rep-targets", json={
            "rep_id": "rep-1", "period_type": "monthly", "period_key": "2026-09", "target_amount": -1.0,
        })
        assert resp.status_code == 422


def test_get_opportunities_flags_is_aging_for_stale_detected_opportunity():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas")
        stale = Opportunity(
            company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")],
            first_detected_at="2020-01-01T00:00:00+00:00",
        )
        fresh = Opportunity(company_id=company.id, type="service", sources=[SourceRef(type="rule_engine")])

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, stale)
                await save_opportunity(session, fresh)
        asyncio.run(seed())

        body = {o["id"]: o for o in client.get("/modules/lead_tracker/opportunities").json()}
        assert body[stale.id]["is_aging"] is True
        assert body[fresh.id]["is_aging"] is False


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


def test_get_opportunities_embeds_account_health_and_qbr_suggestion():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas")
        opportunity = Opportunity(
            company_id=company.id, type="cross-sell", confidence_score=0.9,
            sources=[SourceRef(type="rule_engine")],
        )

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
        asyncio.run(seed())

        body = client.get("/modules/lead_tracker/opportunities").json()[0]
        # sem last_activity_at mas com confidence 0.9 de oportunidade aberta -> só o eixo de
        # confiança conta (nunca "dados_insuficientes" quando há pelo menos um dado real)
        assert body["account_health"] == "verde"
        assert body["renewal_date"] is None
        assert isinstance(body["qbr_suggested_days"], int)
        assert body["qbr_reason"]


def test_patch_company_renewal_date_round_trips_and_reflects_in_opportunities():
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
            f"/modules/lead_tracker/companies/{company.id}/renewal-date",
            json={"renewal_date": "2026-12-01T00:00:00+00:00"},
        )
        assert resp.status_code == 200
        assert resp.json()["renewal_date"].startswith("2026-12-01")

        body = client.get("/modules/lead_tracker/opportunities").json()[0]
        assert body["renewal_date"].startswith("2026-12-01")


def test_patch_company_renewal_date_returns_friendly_404_for_unknown_id():
    with _TempDb():
        resp = client.patch(
            "/modules/lead_tracker/companies/id-inexistente/renewal-date",
            json={"renewal_date": None},
        )
        assert resp.status_code == 404
        assert "não encontrada" in resp.json()["detail"]


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


def test_patch_opportunity_status_one_step_advance_needs_no_note():
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
            f"/modules/lead_tracker/opportunities/{opportunity.id}/status",
            json={"new_status": "qualified"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "qualified"


def test_patch_opportunity_status_big_skip_without_note_is_rejected():
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
            f"/modules/lead_tracker/opportunities/{opportunity.id}/status",
            json={"new_status": "opportunity"},
        )
        assert resp.status_code == 422
        assert "justificativa" in resp.json()["detail"]

        resp_with_note = client.patch(
            f"/modules/lead_tracker/opportunities/{opportunity.id}/status",
            json={"new_status": "opportunity", "note": "Cliente já assinou, fechamos direto."},
        )
        assert resp_with_note.status_code == 200
        assert resp_with_note.json()["status"] == "opportunity"


def test_patch_opportunity_status_returns_friendly_404_for_unknown_id():
    with _TempDb():
        resp = client.patch(
            "/modules/lead_tracker/opportunities/id-inexistente/status",
            json={"new_status": "qualified"},
        )
        assert resp.status_code == 404
        assert "não encontrada" in resp.json()["detail"]


def test_patch_opportunity_status_to_dismissed_without_reason_is_rejected():
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
            f"/modules/lead_tracker/opportunities/{opportunity.id}/status",
            json={"new_status": "dismissed"},
        )
        assert resp.status_code == 422
        assert "motivo" in resp.json()["detail"]

        resp_with_reason = client.patch(
            f"/modules/lead_tracker/opportunities/{opportunity.id}/status",
            json={"new_status": "dismissed", "dismissal_reason": "not_fit"},
        )
        assert resp_with_reason.status_code == 200
        assert resp_with_reason.json()["status"] == "dismissed"
        assert resp_with_reason.json()["dismissal_reason"] == "not_fit"


def test_patch_opportunity_status_reopening_dismissed_clears_reason_in_response():
    with _TempDb() as db:
        import asyncio
        company = Company(name="Aurora Sistemas")
        opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

        async def seed():
            async with db.session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
        asyncio.run(seed())

        client.patch(
            f"/modules/lead_tracker/opportunities/{opportunity.id}/status",
            json={"new_status": "dismissed", "dismissal_reason": "no_evidence"},
        )
        resp = client.patch(
            f"/modules/lead_tracker/opportunities/{opportunity.id}/status",
            json={"new_status": "qualified", "note": "Novo sinal encontrado, reabrindo."},
        )
        assert resp.status_code == 200
        assert resp.json()["dismissal_reason"] is None


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
    test_get_dashboard_metrics_reads_snapshot_and_excludes_zombie_from_weighted_potential()
    test_dashboard_metrics_rep_without_target_shows_no_coverage_ratio()
    test_dashboard_metrics_reads_coverage_from_configured_rep_target()
    test_post_rep_target_same_rep_period_upserts()
    test_get_icp_profile_before_any_save_returns_all_none_never_404()
    test_put_icp_profile_round_trips_and_upserts()
    test_put_icp_profile_rejects_negative_radius()
    test_get_icp_suggestion_returns_null_without_any_satisfied_customer()
    test_get_icp_suggestion_reflects_satisfied_customers()
    test_post_rep_target_rejects_period_key_that_does_not_match_period_type()
    test_post_rep_target_rejects_negative_amount()
    test_sync_endpoint_with_no_source_enabled_returns_empty_list()
    test_sync_endpoint_reads_isolated_env_never_the_real_module_env()
    test_get_opportunities_includes_risk_flag()
    test_get_opportunities_includes_severity_band_not_avaliado_by_default()
    test_get_opportunities_embeds_account_health_and_qbr_suggestion()
    test_get_opportunities_flags_is_aging_for_stale_detected_opportunity()
    test_patch_company_renewal_date_round_trips_and_reflects_in_opportunities()
    test_patch_company_renewal_date_returns_friendly_404_for_unknown_id()
    test_patch_opportunity_qualification_updates_and_recomputes_severity_band()
    test_patch_opportunity_qualification_returns_friendly_404_for_unknown_id()
    test_patch_opportunity_qualification_rejects_value_outside_the_three_options()
    test_patch_opportunity_status_one_step_advance_needs_no_note()
    test_patch_opportunity_status_big_skip_without_note_is_rejected()
    test_patch_opportunity_status_returns_friendly_404_for_unknown_id()
    test_patch_opportunity_status_to_dismissed_without_reason_is_rejected()
    test_patch_opportunity_status_reopening_dismissed_clears_reason_in_response()
    test_get_products_and_services_return_catalog()
    test_post_rule_creates_and_get_rules_lists_it()
    test_post_rule_without_any_evidence_mechanism_returns_friendly_error()
    print("OK — todos os testes HTTP de dado real passaram")
