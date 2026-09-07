"""Testes de integração de persistência (SQLite real via aiosqlite,
arquivo temporário — nunca o banco real do módulo)."""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import create_engine, init_db, make_session_factory
from datetime import date, datetime, timedelta, timezone

from core.models import (
    Address, Company, CompanySignal, Contact, ContextNote, DismissalReason, DismissalReasonRequiredError,
    FieldMapping, ICPProfile, Opportunity, OpportunityStatus, OpportunityStatusChange, PeriodType, Portfolio,
    RepTarget, SemanticFieldRole, SourceRef, StatusChangeRequiresJustificationError, Vendor,
)
from core.opportunity_engine import CorrelationRule, evaluate_rules, field_mapping_id, rep_target_id
from core.repository import (
    count_geo_discoveries_today, delete_field_mapping, get_company, get_icp_profile, get_opportunity,
    get_portfolio_by_company, list_active_rules, list_companies, list_company_signals, list_contacts,
    list_field_mappings, list_latest_snapshot, list_opportunities, list_opportunity_status_changes,
    list_rep_targets, list_rules, list_vendors, recompute_daily_snapshot, save_company, save_company_signal,
    save_contact, save_field_mapping, save_icp_profile, save_opportunity, save_opportunity_status_change,
    save_portfolio, save_rep_target, save_rule, save_vendor, update_company_renewal_date,
    update_opportunity_qualification, update_opportunity_status,
)


async def _fresh_session_factory(tmp_dir: str):
    engine = create_engine(Path(tmp_dir) / "test.db")
    await init_db(engine)
    return make_session_factory(engine)


def test_company_round_trip_preserves_sources_and_timestamps():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas", is_customer=True, sources=[SourceRef(type="salesforce", confidence=1.0)])

            async with session_factory() as session:
                await save_company(session, company)

            async with session_factory() as session:
                loaded = await get_company(session, company.id)

            assert loaded is not None
            assert loaded.name == "Aurora Sistemas"
            assert loaded.is_customer is True
            assert loaded.sources[0].type == "salesforce"
            assert loaded.created_at == company.created_at

    asyncio.run(run())


def test_company_round_trip_preserves_account_standard_fields():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(
                name="Aurora Sistemas", industry="Varejo", annual_revenue=2_500_000.0, employee_count=80,
                address=Address(city="Curitiba", state="PR", postal_code="80010-000", country="Brasil"),
            )

            async with session_factory() as session:
                await save_company(session, company)
            async with session_factory() as session:
                loaded = await get_company(session, company.id)

            assert loaded.industry == "Varejo"
            assert loaded.annual_revenue == 2_500_000.0
            assert loaded.employee_count == 80
            assert loaded.address == Address(city="Curitiba", state="PR", postal_code="80010-000", country="Brasil")

    asyncio.run(run())


def test_company_round_trip_account_standard_fields_default_to_none():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")

            async with session_factory() as session:
                await save_company(session, company)
            async with session_factory() as session:
                loaded = await get_company(session, company.id)

            assert loaded.industry is None
            assert loaded.annual_revenue is None
            assert loaded.employee_count is None
            assert loaded.address is None

    asyncio.run(run())


def test_get_company_returns_none_when_not_found():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                result = await get_company(session, "nao-existe")
            assert result is None

    asyncio.run(run())


def test_save_company_twice_upserts_not_duplicates():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora")

            async with session_factory() as session:
                await save_company(session, company)
            async with session_factory() as session:
                updated = company.model_copy(update={"is_customer": True})
                await save_company(session, updated)

            async with session_factory() as session:
                all_companies = await list_companies(session)

            assert len(all_companies) == 1
            assert all_companies[0].is_customer is True

    asyncio.run(run())


def test_portfolio_round_trip_by_company_id():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            portfolio = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])

            async with session_factory() as session:
                await save_portfolio(session, portfolio)

            async with session_factory() as session:
                loaded = await get_portfolio_by_company(session, "c1")

            assert loaded is not None
            assert loaded.product_ids == ["veeam_vbr", "m365"]

    asyncio.run(run())


def test_end_to_end_portfolio_to_rule_engine_to_persisted_opportunity():
    """Fluxo completo: salva empresa+portfólio real, roda o motor de regras
    sobre o portfólio carregado do banco, persiste a oportunidade
    resultante e recarrega — prova que a lacuna de persistência fechou de
    ponta a ponta, não só por tabela isolada."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)

            company = Company(name="Aurora Sistemas", is_customer=True)
            vendor = Vendor(name="Veeam")
            portfolio = Portfolio(company_id=company.id, product_ids=["veeam_vbr", "m365"])

            async with session_factory() as session:
                await save_company(session, company)
                await save_vendor(session, vendor)
                await save_portfolio(session, portfolio)

            async with session_factory() as session:
                loaded_portfolio = await get_portfolio_by_company(session, company.id)

            rule = CorrelationRule(
                id="veeam_m365_sem_vdc365", opportunity_type="cross-sell",
                requires=["veeam_vbr", "m365"], absent=["vdc365"],
                justification="Tem Veeam VBR e M365, sem VDC365.",
            )
            opportunities = evaluate_rules(loaded_portfolio, [rule])
            assert len(opportunities) == 1

            async with session_factory() as session:
                await save_opportunity(session, opportunities[0])

            async with session_factory() as session:
                persisted = await list_opportunities(session, company_id=company.id)

            assert len(persisted) == 1
            assert persisted[0].status == OpportunityStatus.DETECTED
            assert persisted[0].evidence == ["veeam_vbr", "m365"]

    asyncio.run(run())


def test_update_opportunity_qualification_round_trip():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)

            async with session_factory() as session:
                updated = await update_opportunity_qualification(
                    session, opportunity.id, "parcial", "critico_interno", "Só afeta a filial SP.",
                )

            assert updated.scope_note == "parcial"
            assert updated.criticality == "critico_interno"
            assert updated.severity_note == "Só afeta a filial SP."

            async with session_factory() as session:
                persisted = await list_opportunities(session, company_id=company.id)
            assert persisted[0].scope_note == "parcial"

    asyncio.run(run())


def test_update_opportunity_qualification_returns_none_for_unknown_id():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                result = await update_opportunity_qualification(session, "id-inexistente", "isolado", "nao_critico", None)
            assert result is None

    asyncio.run(run())


def test_save_opportunity_never_overwrites_manually_filled_qualification():
    """Regressão crítica encontrada pelo agente Plan antes de shipar esta
    fatia: o motor (save_opportunity, chamado a cada /sync) nunca sabe de
    scope_note/criticality/severity_note — sem proteção, o segundo sync
    apagaria o que o vendedor preencheu manualmente entre uma sincronização
    e outra."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)  # 1º sync

            async with session_factory() as session:
                await update_opportunity_qualification(
                    session, opportunity.id, "generalizado", "critico_exposto", "Preenchido pelo vendedor.",
                )

            # 2º sync reavaliando a mesma oportunidade (motor nunca seta os 3 campos manuais)
            async with session_factory() as session:
                await save_opportunity(session, opportunity)

            async with session_factory() as session:
                persisted = await list_opportunities(session, company_id=company.id)
            assert persisted[0].scope_note == "generalizado"
            assert persisted[0].criticality == "critico_exposto"
            assert persisted[0].severity_note == "Preenchido pelo vendedor."

    asyncio.run(run())


def test_update_opportunity_status_round_trip_writes_history_with_note():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)

            async with session_factory() as session:
                updated = await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.CONTACTED, note="Pulou pra contacted, já tinha reunião marcada.",
                )
            assert updated.status == OpportunityStatus.CONTACTED

            async with session_factory() as session:
                persisted = await get_opportunity(session, opportunity.id)
                history = await list_opportunity_status_changes(session, opportunity.id)
            assert persisted.status == OpportunityStatus.CONTACTED
            assert len(history) == 1
            assert history[0].status == OpportunityStatus.CONTACTED
            assert history[0].note == "Pulou pra contacted, já tinha reunião marcada."

    asyncio.run(run())


def test_update_opportunity_status_returns_none_for_unknown_id():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                result = await update_opportunity_status(session, "id-inexistente", OpportunityStatus.QUALIFIED)
            assert result is None

    asyncio.run(run())


def test_update_opportunity_status_same_status_is_noop_and_writes_no_history():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await update_opportunity_status(session, opportunity.id, OpportunityStatus.DETECTED)

            async with session_factory() as session:
                history = await list_opportunity_status_changes(session, opportunity.id)
            assert history == []

    asyncio.run(run())


def test_update_opportunity_status_checks_justification_against_the_real_current_status():
    """Regressão do TOCTOU apontado na revisão de código: a rota antes lia o
    status atual numa consulta separada, decidia se precisava de
    justificativa, e só então chamava update_opportunity_status (que fazia
    sua PRÓPRIA busca) — entre as duas leituras, o status real podia mudar
    (ex. outra aba do navegador reabrindo/avançando a oportunidade),
    enganando a decisão. Agora a checagem roda contra a MESMA linha que a
    função acabou de buscar, então a exigência de justificativa é sempre
    calculada contra o dado real persistido no momento da escrita, nunca
    uma crença desatualizada do chamador."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.DISMISSED, dismissal_reason=DismissalReason.NOT_FIT,
                )  # status real: dismissed

            # sem nota — reabrir "dismissed" sempre exige justificativa,
            # mesmo que o chamador não soubesse que o status real era esse
            async with session_factory() as session:
                raised = False
                try:
                    await update_opportunity_status(session, opportunity.id, OpportunityStatus.CONTACTED, note=None)
                except StatusChangeRequiresJustificationError:
                    raised = True
                assert raised

            async with session_factory() as session:
                persisted = await get_opportunity(session, opportunity.id)
            assert persisted.status == OpportunityStatus.DISMISSED  # nunca mudou

    asyncio.run(run())


def test_update_opportunity_status_to_dismissed_requires_categorized_reason():
    """Módulo 6 (Fase D) — consulta ao agente Pipeline Analyst sobre a
    taxonomia. Sem `dismissal_reason`, `dismissed` vira beco sem saída pra
    qualquer relatório futuro de "por que perdemos oportunidades"."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)

            async with session_factory() as session:
                raised = False
                try:
                    await update_opportunity_status(session, opportunity.id, OpportunityStatus.DISMISSED)
                except DismissalReasonRequiredError:
                    raised = True
                assert raised

            async with session_factory() as session:
                persisted = await get_opportunity(session, opportunity.id)
            assert persisted.status == OpportunityStatus.DETECTED  # nunca mudou sem o motivo

    asyncio.run(run())


def test_update_opportunity_status_to_dismissed_persists_categorized_reason():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                updated = await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.DISMISSED,
                    dismissal_reason=DismissalReason.FALSE_POSITIVE,
                )
            assert updated.dismissal_reason == DismissalReason.FALSE_POSITIVE

            async with session_factory() as session:
                persisted = await get_opportunity(session, opportunity.id)
            assert persisted.dismissal_reason == DismissalReason.FALSE_POSITIVE

    asyncio.run(run())


def test_reopening_dismissed_opportunity_clears_stale_dismissal_reason():
    """`dismissal_reason` só faz sentido enquanto status==dismissed — um
    relatório que lesse esse campo depois de reaberta veria um motivo de um
    descarte que já foi revertido, dado enganoso."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.DISMISSED,
                    dismissal_reason=DismissalReason.NO_EVIDENCE,
                )
                reopened = await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.QUALIFIED, note="Novo sinal encontrado, reabrindo.",
                )
            assert reopened.dismissal_reason is None

    asyncio.run(run())


def test_dismissal_reason_history_survives_reopen_and_second_dismissal():
    """Achado da revisão de código: `Opportunity.dismissal_reason` é limpo
    ao reabrir (só faz sentido enquanto status==dismissed), então guardar o
    motivo SÓ ali apagaria irrecuperavelmente o motivo do 1º descarte assim
    que a oportunidade fosse reaberta e descartada de novo com outro
    motivo. A linha de histórico (`OpportunityStatusChange`) preserva os
    dois, cada um na transição em que aconteceu."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.DISMISSED,
                    dismissal_reason=DismissalReason.NO_EVIDENCE,
                )
                await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.QUALIFIED, note="Reabrindo, novo sinal.",
                )
                await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.DISMISSED,
                    dismissal_reason=DismissalReason.NOT_FIT,
                )

            async with session_factory() as session:
                history = await list_opportunity_status_changes(session, opportunity.id)
            dismissed_entries = [h for h in history if h.status == OpportunityStatus.DISMISSED]
            assert [h.dismissal_reason for h in dismissed_entries] == [DismissalReason.NO_EVIDENCE, DismissalReason.NOT_FIT]

    asyncio.run(run())


def test_recompute_daily_snapshot_reflects_current_opportunity_state():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas", rep_id="rep-1", segment="enterprise")
            opportunity = Opportunity(
                company_id=company.id, type="cross-sell", financial_potential=10000, confidence_score=0.8,
                sources=[SourceRef(type="salesforce")],
            )

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await recompute_daily_snapshot(session, today=date(2026, 9, 5))

            async with session_factory() as session:
                snapshot = await list_latest_snapshot(session)
            assert len(snapshot) == 1
            row = snapshot[0]
            assert row.opportunity_id == opportunity.id
            assert row.snapshot_date == date(2026, 9, 5)
            assert row.stage == OpportunityStatus.DETECTED
            assert row.financial_potential == 10000
            assert row.confidence_score == 0.8
            assert row.rep_id == "rep-1"
            assert row.segment == "enterprise"
            assert row.source == "salesforce"
            assert row.is_zombie is False  # synced_at recente, sem histórico de status

    asyncio.run(run())


def test_recompute_daily_snapshot_twice_same_day_upserts_not_duplicates():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await recompute_daily_snapshot(session, today=date(2026, 9, 5))
                await update_opportunity_status(session, opportunity.id, OpportunityStatus.QUALIFIED)
                await recompute_daily_snapshot(session, today=date(2026, 9, 5))  # mesmo dia, 2º /sync

            async with session_factory() as session:
                snapshot = await list_latest_snapshot(session)
            assert len(snapshot) == 1  # upsert, nunca duplica
            assert snapshot[0].stage == OpportunityStatus.QUALIFIED  # reflete o estado mais recente

    asyncio.run(run())


def test_recompute_daily_snapshot_flags_zombie_via_status_history_fallback_to_first_detected_at():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            old = datetime.now(timezone.utc) - timedelta(days=45)
            opportunity = Opportunity(
                company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")],
                first_detected_at=old,
            )

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)
                await recompute_daily_snapshot(session)

            async with session_factory() as session:
                snapshot = await list_latest_snapshot(session)
            assert snapshot[0].is_zombie is True  # sem histórico de status, usa first_detected_at (45 dias > 30)

    asyncio.run(run())


def test_recompute_daily_snapshot_zombie_survives_repeated_resync_never_touched_by_a_human():
    """Regressão do achado crítico da revisão de código: synced_at é
    reescrito a cada /sync que ainda detecta a oportunidade — se o fallback
    de zumbi usasse esse campo, uma oportunidade nunca triada por ninguém
    pareceria sempre "fresca" porque o motor renova o timestamp a cada
    ciclo, e o zumbi nunca dispararia pra exatamente a população que deveria
    capturar. first_detected_at nunca é reescrito, então 2 re-syncs
    (equivalente a rodar /sync várias vezes ao longo de semanas) não deve
    mudar o resultado."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            old = datetime.now(timezone.utc) - timedelta(days=45)
            opportunity = Opportunity(
                company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")],
                first_detected_at=old,
            )

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)  # 1º sync — grava first_detected_at

            # simula um 2º /sync bem depois: mesmo objeto de domínio, mas
            # synced_at "renovado" pra agora (exatamente o que o motor faz)
            resynced = opportunity.model_copy(update={"synced_at": datetime.now(timezone.utc)})
            async with session_factory() as session:
                await save_opportunity(session, resynced)
                await recompute_daily_snapshot(session)

            async with session_factory() as session:
                snapshot = await list_latest_snapshot(session)
                persisted = await get_opportunity(session, opportunity.id)
            assert persisted.first_detected_at == old  # nunca reescrito pelo 2º sync
            assert snapshot[0].is_zombie is True  # continua zumbi, não "renovou" com o re-sync

    asyncio.run(run())


def test_list_latest_snapshot_returns_empty_when_no_snapshot_ever_ran():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                snapshot = await list_latest_snapshot(session)
            assert snapshot == []

    asyncio.run(run())


def test_save_opportunity_never_resets_manually_advanced_status_on_resync():
    """Regressão do achado da Fase D: o motor sempre constrói a oportunidade
    em `detected` e o id é determinístico — sem excluir `status` do `SET`
    do upsert, rodar `/sync` de novo pra empresa com o mesmo portfólio
    resetaria pra `detected` qualquer oportunidade já avançada manualmente."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)  # 1º sync — nasce em detected
                await update_opportunity_status(session, opportunity.id, OpportunityStatus.QUALIFIED)

            async with session_factory() as session:
                await save_opportunity(session, opportunity)  # 2º sync — motor ainda constrói em "detected"

            async with session_factory() as session:
                persisted = await get_opportunity(session, opportunity.id)
            assert persisted.status == OpportunityStatus.QUALIFIED

    asyncio.run(run())


def test_save_opportunity_never_resets_dismissal_reason_on_resync():
    """Mesma classe de regressão do teste acima, agora pro módulo 6: o
    motor nunca sabe de `dismissal_reason` — `save_opportunity` (upsert do
    `/sync`) precisa continuar excluindo essa coluna do `SET`, senão um
    `/sync` que roda depois de um descarte manual apagaria o motivo
    categorizado."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)  # 1º sync — nasce em detected
                await update_opportunity_status(
                    session, opportunity.id, OpportunityStatus.DISMISSED,
                    dismissal_reason=DismissalReason.NOT_QUALIFIED,
                )

            async with session_factory() as session:
                await save_opportunity(session, opportunity)  # 2º sync — motor ainda constrói em "detected"

            async with session_factory() as session:
                persisted = await get_opportunity(session, opportunity.id)
            assert persisted.status == OpportunityStatus.DISMISSED
            assert persisted.dismissal_reason == DismissalReason.NOT_QUALIFIED

    asyncio.run(run())


def test_save_opportunity_concurrent_with_qualification_update_never_reverts_it():
    """Regressão do TOCTOU apontado na revisão de código: a versão anterior de
    save_opportunity lia o registro existente e só depois fazia merge — entre
    as duas awaits, um update_opportunity_qualification concorrente podia ser
    sobrescrito pelos valores antigos lidos antes dele. Upsert atômico
    (INSERT ... ON CONFLICT DO UPDATE sem os 3 campos manuais no SET) fecha a
    janela; roda save_opportunity e update_opportunity_qualification em
    paralelo repetidas vezes pra garantir que a ordem de conclusão nunca
    reverte o campo manual."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            opportunity = Opportunity(company_id=company.id, type="cross-sell", sources=[SourceRef(type="rule_engine")])

            async with session_factory() as session:
                await save_company(session, company)
                await save_opportunity(session, opportunity)  # cria a linha

            for _ in range(20):
                async def do_save():
                    async with session_factory() as session:
                        await save_opportunity(session, opportunity)

                async def do_update():
                    async with session_factory() as session:
                        await update_opportunity_qualification(
                            session, opportunity.id, "generalizado", "critico_exposto", "Preenchido pelo vendedor.",
                        )

                await asyncio.gather(do_save(), do_update())

                async with session_factory() as session:
                    persisted = await list_opportunities(session, company_id=company.id)
                assert persisted[0].scope_note == "generalizado"
                assert persisted[0].criticality == "critico_exposto"

    asyncio.run(run())


def test_company_last_activity_at_round_trip():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            when = datetime(2026, 8, 1, tzinfo=timezone.utc)
            company = Company(name="Aurora Sistemas", last_activity_at=when)

            async with session_factory() as session:
                await save_company(session, company)

            async with session_factory() as session:
                loaded = await get_company(session, company.id)

            assert loaded.last_activity_at == when

    asyncio.run(run())


def test_update_company_renewal_date_round_trip():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            when = datetime(2026, 12, 1, tzinfo=timezone.utc)

            async with session_factory() as session:
                await save_company(session, company)
                updated = await update_company_renewal_date(session, company.id, when)
            assert updated.renewal_date == when

            async with session_factory() as session:
                loaded = await get_company(session, company.id)
            assert loaded.renewal_date == when

    asyncio.run(run())


def test_update_company_renewal_date_returns_none_for_unknown_id():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                result = await update_company_renewal_date(session, "id-inexistente", datetime.now(timezone.utc))
            assert result is None

    asyncio.run(run())


def test_save_company_never_reverts_renewal_date_from_a_stale_in_memory_snapshot():
    """Regressão do TOCTOU apontado na revisão de código: backend/sync.py
    mantém o Company em memória (capturado ANTES de qualquer edição manual
    concorrente) durante todo o /sync, só chamando save_company no fim. Se
    um update_company_renewal_date comitar nesse meio-tempo, um save_company
    que fizesse merge da linha inteira reverteria a edição pro valor antigo
    capturado em memória — upsert atômico que nunca lista renewal_date no
    SET fecha essa janela, igual ao fix já aplicado em save_opportunity."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")

            async with session_factory() as session:
                await save_company(session, company)

            # snapshot capturado ANTES da edição manual — simula o que
            # backend/sync.py mantém em memória durante um /sync em andamento
            stale_snapshot = company.model_copy(update={"last_activity_at": datetime.now(timezone.utc)})

            when = datetime(2026, 12, 1, tzinfo=timezone.utc)
            async with session_factory() as session:
                await update_company_renewal_date(session, company.id, when)  # edição concorrente "chega primeiro"

            async with session_factory() as session:
                await save_company(session, stale_snapshot)  # sync termina com o snapshot antigo (renewal_date=None)

            async with session_factory() as session:
                after = await get_company(session, company.id)
            assert after.renewal_date == when

    asyncio.run(run())


def test_contact_seniority_tier_round_trip():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            contact = Contact(company_id=company.id, name="Fulano", seniority_tier="decisor")

            async with session_factory() as session:
                await save_company(session, company)
                await save_contact(session, contact)

            async with session_factory() as session:
                contacts = await list_contacts(session, company.id)

            assert contacts[0].seniority_tier == "decisor"

    asyncio.run(run())


def test_opportunity_rich_evidence_fields_round_trip():
    """Fase C, Fatia 3 — evidence_summary/discovery_prompt/synced_at
    persistem e voltam intactos."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            portfolio = Portfolio(company_id=company.id, product_ids=["veeam_vbr", "m365"])
            rule = CorrelationRule(
                id="veeam_m365_sem_vdc365", opportunity_type="cross-sell",
                requires=["veeam_vbr", "m365"], absent=["vdc365"],
                justification="Tem Veeam VBR e M365, sem VDC365.",
                discovery_prompt="Por que a proteção VDC365 nunca foi priorizada?",
            )
            opportunities = evaluate_rules(portfolio, [rule])

            async with session_factory() as session:
                await save_opportunity(session, opportunities[0])

            async with session_factory() as session:
                persisted = await list_opportunities(session, company_id=company.id)

            assert persisted[0].evidence_summary == opportunities[0].evidence_summary
            assert "[FATO]" in persisted[0].evidence_summary
            assert "[OPORTUNIDADE]" in persisted[0].evidence_summary
            assert "[FONTE]" in persisted[0].evidence_summary
            assert persisted[0].discovery_prompt == "Por que a proteção VDC365 nunca foi priorizada?"
            assert persisted[0].synced_at == opportunities[0].synced_at

    asyncio.run(run())


def test_company_fase_b_fields_round_trip():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(
                name="Aurora Sistemas", rep_id="rep-1", segment="média", region="sudeste",
                trigger_event=ContextNote(text="Renovação em 30 dias", source=SourceRef(type="salesforce")),
                attempted_solutions=[ContextNote(text="Tentou backup manual", source=SourceRef(type="manual"))],
                strategic_context=ContextNote(text="Expansão para novo escritório", source=SourceRef(type="website")),
            )

            async with session_factory() as session:
                await save_company(session, company)
            async with session_factory() as session:
                loaded = await get_company(session, company.id)

            assert loaded.rep_id == "rep-1"
            assert loaded.segment == "média"
            assert loaded.trigger_event.text == "Renovação em 30 dias"
            assert loaded.attempted_solutions[0].source.type == "manual"
            assert loaded.strategic_context.text == "Expansão para novo escritório"

    asyncio.run(run())


def test_company_without_fase_b_fields_round_trips_as_none():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora")

            async with session_factory() as session:
                await save_company(session, company)
            async with session_factory() as session:
                loaded = await get_company(session, company.id)

            assert loaded.trigger_event is None
            assert loaded.attempted_solutions == []

    asyncio.run(run())


def test_company_signal_round_trip():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            signal = CompanySignal(
                company_id="c1", signal_type="renewal_upcoming",
                evidence=["contrato vence em 2026-10-01"], source=SourceRef(type="salesforce"),
            )

            async with session_factory() as session:
                await save_company_signal(session, signal)
            async with session_factory() as session:
                loaded = await list_company_signals(session, "c1")

            assert len(loaded) == 1
            assert loaded[0].signal_type == "renewal_upcoming"
            assert loaded[0].status == "open"

    asyncio.run(run())


def test_opportunity_status_change_round_trip():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            change = OpportunityStatusChange(opportunity_id="o1", status=OpportunityStatus.QUALIFIED)

            async with session_factory() as session:
                await save_opportunity_status_change(session, change)
            async with session_factory() as session:
                loaded = await list_opportunity_status_changes(session, "o1")

            assert len(loaded) == 1
            assert loaded[0].status == OpportunityStatus.QUALIFIED

    asyncio.run(run())


def test_correlation_rule_round_trip():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            rule = CorrelationRule(
                id="backup_sem_monitoring", opportunity_type="cross-sell",
                requires_category=["backup"], absent_category=["monitoring"],
                justification="Tem backup, sem monitoramento.", active=False,
            )

            async with session_factory() as session:
                await save_rule(session, rule)
            async with session_factory() as session:
                loaded = await list_rules(session)

            assert len(loaded) == 1
            assert loaded[0].requires_category == ["backup"]
            assert loaded[0].active is False

    asyncio.run(run())


def test_list_active_rules_filters_inactive():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            active = CorrelationRule(id="ativa", opportunity_type="x", requires=["a"], justification="j")
            inactive = CorrelationRule(id="inativa", opportunity_type="x", requires=["a"], justification="j", active=False)

            async with session_factory() as session:
                await save_rule(session, active)
                await save_rule(session, inactive)
            async with session_factory() as session:
                loaded = await list_active_rules(session)

            assert [r.id for r in loaded] == ["ativa"]

    asyncio.run(run())


def test_opportunity_risk_flag_round_trips():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            opportunity = Opportunity(
                company_id="c1", type="risk", risk_flag="vdc365 vendido sem assessment.",
                sources=[SourceRef(type="rule_engine")],
            )

            async with session_factory() as session:
                await save_opportunity(session, opportunity)
            async with session_factory() as session:
                loaded = await list_opportunities(session, company_id="c1")

            assert loaded[0].risk_flag == "vdc365 vendido sem assessment."

    asyncio.run(run())


def test_save_rep_target_round_trips():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            target = RepTarget(
                id=rep_target_id("rep-1", PeriodType.MONTHLY, "2026-09"),
                rep_id="rep-1", period_type=PeriodType.MONTHLY, period_key="2026-09", target_amount=50000.0,
            )
            async with session_factory() as session:
                await save_rep_target(session, target)
                loaded = await list_rep_targets(session, PeriodType.MONTHLY, "2026-09")
            assert len(loaded) == 1
            assert loaded[0].rep_id == "rep-1"
            assert loaded[0].target_amount == 50000.0

    asyncio.run(run())


def test_save_rep_target_same_rep_period_is_upsert_never_duplicate():
    """Id determinístico (rep_target_id) — recadastrar meta pro mesmo
    rep+período atualiza, nunca cria uma 2ª linha concorrente."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                await save_rep_target(session, RepTarget(
                    id=rep_target_id("rep-1", PeriodType.MONTHLY, "2026-09"),
                    rep_id="rep-1", period_type=PeriodType.MONTHLY, period_key="2026-09", target_amount=50000.0,
                ))
                await save_rep_target(session, RepTarget(
                    id=rep_target_id("rep-1", PeriodType.MONTHLY, "2026-09"),
                    rep_id="rep-1", period_type=PeriodType.MONTHLY, period_key="2026-09", target_amount=75000.0,
                ))
                loaded = await list_rep_targets(session, PeriodType.MONTHLY, "2026-09")
            assert len(loaded) == 1
            assert loaded[0].target_amount == 75000.0

    asyncio.run(run())


def test_save_rep_target_preserves_original_created_at_on_upsert():
    """Achado da revisão de código: recadastrar a mesma meta (upsert)
    reconstrói o `RepTarget` com `created_at=_now()` a cada chamada — sem
    preservar o valor original, a coluna se comportaria como "última
    modificação" apesar do nome."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            first = RepTarget(
                id=rep_target_id("rep-1", PeriodType.MONTHLY, "2026-09"),
                rep_id="rep-1", period_type=PeriodType.MONTHLY, period_key="2026-09", target_amount=50000.0,
            )
            async with session_factory() as session:
                await save_rep_target(session, first)

            second = RepTarget(
                id=rep_target_id("rep-1", PeriodType.MONTHLY, "2026-09"),
                rep_id="rep-1", period_type=PeriodType.MONTHLY, period_key="2026-09", target_amount=75000.0,
            )
            async with session_factory() as session:
                await save_rep_target(session, second)
                loaded = await list_rep_targets(session, PeriodType.MONTHLY, "2026-09")
            assert loaded[0].created_at == first.created_at

    asyncio.run(run())


def test_get_icp_profile_returns_none_before_first_save():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                profile = await get_icp_profile(session)
            assert profile is None

    asyncio.run(run())


def test_save_icp_profile_round_trips():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            profile = ICPProfile(
                reference_product_id="p1", place_category="car_dealer",
                company_size_hint="media", radius_km=25.0, search_origin_address="Av. Paulista, São Paulo",
            )
            async with session_factory() as session:
                await save_icp_profile(session, profile)
                loaded = await get_icp_profile(session)
            assert loaded.reference_product_id == "p1"
            assert loaded.place_category == "car_dealer"
            assert loaded.company_size_hint == "media"
            assert loaded.radius_km == 25.0
            assert loaded.search_origin_address == "Av. Paulista, São Paulo"

    asyncio.run(run())


def test_save_icp_profile_is_singleton_never_duplicates():
    """Salvar de novo (reconfigurar o ICP) é upsert na mesma linha —
    id fixo 'icp_profile', nunca uma 2ª configuração concorrente."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                await save_icp_profile(session, ICPProfile(place_category="car_dealer", radius_km=10.0))
                await save_icp_profile(session, ICPProfile(place_category="restaurant", radius_km=20.0))
                loaded = await get_icp_profile(session)
            assert loaded.place_category == "restaurant"
            assert loaded.radius_km == 20.0

    asyncio.run(run())


def test_save_field_mapping_round_trips():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            mapping = FieldMapping(
                id=field_mapping_id("salesforce", "Segmento__c"), provider_id="salesforce",
                source_field_api_name="Segmento__c", source_field_label="Segmento",
                role=SemanticFieldRole.INDUSTRY_HINT,
            )
            async with session_factory() as session:
                await save_field_mapping(session, mapping)
                loaded = await list_field_mappings(session, "salesforce")
            assert len(loaded) == 1
            assert loaded[0].source_field_api_name == "Segmento__c"
            assert loaded[0].role == SemanticFieldRole.INDUSTRY_HINT

    asyncio.run(run())


def test_save_field_mapping_same_field_upserts_never_duplicates():
    """Reconfigurar o papel do mesmo campo (mesmo provider+api_name) é
    upsert na mesma linha (id determinístico), nunca um 2º mapeamento
    concorrente pro mesmo campo."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("salesforce", "Segmento__c"), provider_id="salesforce",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.INDUSTRY_HINT,
                ))
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("salesforce", "Segmento__c"), provider_id="salesforce",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.DEAL_SIZE_HINT,
                ))
                loaded = await list_field_mappings(session, "salesforce")
            assert len(loaded) == 1
            assert loaded[0].role == SemanticFieldRole.DEAL_SIZE_HINT

    asyncio.run(run())


def test_list_field_mappings_filters_by_provider():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("salesforce", "A__c"), provider_id="salesforce",
                    source_field_api_name="A__c", source_field_label="A", role=SemanticFieldRole.INDUSTRY_HINT,
                ))
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("website", "A__c"), provider_id="website",
                    source_field_api_name="A__c", source_field_label="A", role=SemanticFieldRole.RENEWAL_DATE,
                ))
                loaded = await list_field_mappings(session, "salesforce")
            assert len(loaded) == 1
            assert loaded[0].provider_id == "salesforce"

    asyncio.run(run())


def test_delete_field_mapping_removes_it():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            mapping_id = field_mapping_id("salesforce", "Segmento__c")
            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=mapping_id, provider_id="salesforce", source_field_api_name="Segmento__c",
                    source_field_label="Segmento", role=SemanticFieldRole.INDUSTRY_HINT,
                ))
                await delete_field_mapping(session, mapping_id)
                loaded = await list_field_mappings(session, "salesforce")
            assert loaded == []

    asyncio.run(run())


def test_delete_field_mapping_unknown_id_is_a_noop():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                await delete_field_mapping(session, "nao-existe")

    asyncio.run(run())


def test_save_field_mapping_rejects_two_different_fields_for_same_role():
    """Achado da revisão de código do módulo 5 — UniqueConstraint(provider_id,
    role) trava no banco a garantia de que só um campo mapeia pra cada
    papel, mesmo se a lógica de reatribuição da rota falhar (ex.: corrida
    entre duas requisições concorrentes)."""
    from sqlalchemy.exc import IntegrityError

    async def run():
        # ignore_cleanup_errors: no Windows, um commit que falha por
        # UniqueConstraint deixa o handle do arquivo SQLite (aiosqlite)
        # preso tempo suficiente pra travar o rmtree do TemporaryDirectory
        # mesmo depois de rollback + engine.dispose() — não é um bug deste
        # teste, é uma particularidade de SQLite+Windows após violação de
        # constraint; ignorar a falha de limpeza aqui é seguro (é um dir
        # temporário, o SO limpa depois).
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            engine = create_engine(Path(tmp) / "test.db")
            await init_db(engine)
            session_factory = make_session_factory(engine)
            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("salesforce", "A__c"), provider_id="salesforce",
                    source_field_api_name="A__c", source_field_label="A", role=SemanticFieldRole.INDUSTRY_HINT,
                ))
                raised = False
                try:
                    await save_field_mapping(session, FieldMapping(
                        id=field_mapping_id("salesforce", "B__c"), provider_id="salesforce",
                        source_field_api_name="B__c", source_field_label="B", role=SemanticFieldRole.INDUSTRY_HINT,
                    ))
                except IntegrityError:
                    raised = True
                    await session.rollback()
                assert raised
            await engine.dispose()

    asyncio.run(run())


def test_count_geo_discoveries_today_counts_only_google_maps_companies_for_that_rep():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            # UTC, nunca date.today() (local) -- Company.created_at é sempre
            # UTC-aware; comparar contra data local é flaky perto da meia-noite
            # em qualquer fuso não-UTC (bug real encontrado rodando a suíte
            # à noite no fuso do Brasil, onde UTC já vira o dia seguinte).
            today = datetime.now(timezone.utc).date()
            geo_company = Company(name="Descoberta", rep_id="rep-1", sources=[SourceRef(type="google_maps")])
            manual_company = Company(name="Manual", rep_id="rep-1", sources=[SourceRef(type="manual")])
            other_rep_company = Company(name="Outro rep", rep_id="rep-2", sources=[SourceRef(type="google_maps")])

            async with session_factory() as session:
                await save_company(session, geo_company)
                await save_company(session, manual_company)
                await save_company(session, other_rep_company)
                count = await count_geo_discoveries_today(session, "rep-1", today)

            assert count == 1  # só geo_company: mesmo rep, fonte google_maps, hoje

    asyncio.run(run())


def test_count_geo_discoveries_today_ignores_other_days():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            old_company = Company(
                name="Antiga", rep_id="rep-1", sources=[SourceRef(type="google_maps")],
                created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
            async with session_factory() as session:
                await save_company(session, old_company)
                count = await count_geo_discoveries_today(session, "rep-1", date.today())
            assert count == 0

    asyncio.run(run())


def test_count_geo_discoveries_today_compares_against_utc_date_not_local():
    """Regressão do achado da revisão de código: a rota chamava
    `date.today()` (data LOCAL do servidor) em vez de
    `datetime.now(timezone.utc).date()` — desalinhava a cota diária
    perto da meia-noite em qualquer servidor fora de UTC. Este teste
    trava o contrato da FUNÇÃO em si: `created_at` gravado logo após a
    meia-noite UTC de hoje precisa contar como "hoje" quando comparado
    contra a data UTC de hoje, não uma data local arbitrária."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            utc_today = datetime.now(timezone.utc).date()
            just_after_utc_midnight = datetime.combine(utc_today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(minutes=5)
            company = Company(
                name="Recém após meia-noite UTC", rep_id="rep-1", sources=[SourceRef(type="google_maps")],
                created_at=just_after_utc_midnight,
            )
            async with session_factory() as session:
                await save_company(session, company)
                count = await count_geo_discoveries_today(session, "rep-1", utc_today)
            assert count == 1

    asyncio.run(run())


def test_list_rep_targets_filters_by_period():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            async with session_factory() as session:
                await save_rep_target(session, RepTarget(
                    id=rep_target_id("rep-1", PeriodType.MONTHLY, "2026-09"),
                    rep_id="rep-1", period_type=PeriodType.MONTHLY, period_key="2026-09", target_amount=50000.0,
                ))
                await save_rep_target(session, RepTarget(
                    id=rep_target_id("rep-1", PeriodType.MONTHLY, "2026-10"),
                    rep_id="rep-1", period_type=PeriodType.MONTHLY, period_key="2026-10", target_amount=60000.0,
                ))
                september = await list_rep_targets(session, PeriodType.MONTHLY, "2026-09")
                october = await list_rep_targets(session, PeriodType.MONTHLY, "2026-10")
            assert [t.target_amount for t in september] == [50000.0]
            assert [t.target_amount for t in october] == [60000.0]

    asyncio.run(run())


if __name__ == "__main__":
    test_company_round_trip_preserves_sources_and_timestamps()
    test_company_round_trip_preserves_account_standard_fields()
    test_company_round_trip_account_standard_fields_default_to_none()
    test_get_company_returns_none_when_not_found()
    test_save_company_twice_upserts_not_duplicates()
    test_portfolio_round_trip_by_company_id()
    test_end_to_end_portfolio_to_rule_engine_to_persisted_opportunity()
    test_company_fase_b_fields_round_trip()
    test_company_without_fase_b_fields_round_trips_as_none()
    test_company_signal_round_trip()
    test_opportunity_status_change_round_trip()
    test_correlation_rule_round_trip()
    test_list_active_rules_filters_inactive()
    test_opportunity_risk_flag_round_trips()
    test_save_rep_target_round_trips()
    test_save_rep_target_same_rep_period_is_upsert_never_duplicate()
    test_save_rep_target_preserves_original_created_at_on_upsert()
    test_get_icp_profile_returns_none_before_first_save()
    test_save_icp_profile_round_trips()
    test_save_icp_profile_is_singleton_never_duplicates()
    test_save_field_mapping_round_trips()
    test_save_field_mapping_same_field_upserts_never_duplicates()
    test_list_field_mappings_filters_by_provider()
    test_delete_field_mapping_removes_it()
    test_delete_field_mapping_unknown_id_is_a_noop()
    test_save_field_mapping_rejects_two_different_fields_for_same_role()
    test_count_geo_discoveries_today_counts_only_google_maps_companies_for_that_rep()
    test_count_geo_discoveries_today_ignores_other_days()
    test_count_geo_discoveries_today_compares_against_utc_date_not_local()
    test_list_rep_targets_filters_by_period()
    test_opportunity_rich_evidence_fields_round_trip()
    test_company_last_activity_at_round_trip()
    test_update_company_renewal_date_round_trip()
    test_update_company_renewal_date_returns_none_for_unknown_id()
    test_save_company_never_reverts_renewal_date_from_a_stale_in_memory_snapshot()
    test_contact_seniority_tier_round_trip()
    test_update_opportunity_qualification_round_trip()
    test_update_opportunity_qualification_returns_none_for_unknown_id()
    test_save_opportunity_never_overwrites_manually_filled_qualification()
    test_update_opportunity_status_round_trip_writes_history_with_note()
    test_update_opportunity_status_returns_none_for_unknown_id()
    test_update_opportunity_status_same_status_is_noop_and_writes_no_history()
    test_update_opportunity_status_checks_justification_against_the_real_current_status()
    test_update_opportunity_status_to_dismissed_requires_categorized_reason()
    test_update_opportunity_status_to_dismissed_persists_categorized_reason()
    test_reopening_dismissed_opportunity_clears_stale_dismissal_reason()
    test_dismissal_reason_history_survives_reopen_and_second_dismissal()
    test_recompute_daily_snapshot_reflects_current_opportunity_state()
    test_recompute_daily_snapshot_twice_same_day_upserts_not_duplicates()
    test_recompute_daily_snapshot_flags_zombie_via_status_history_fallback_to_first_detected_at()
    test_recompute_daily_snapshot_zombie_survives_repeated_resync_never_touched_by_a_human()
    test_list_latest_snapshot_returns_empty_when_no_snapshot_ever_ran()
    test_save_opportunity_never_resets_manually_advanced_status_on_resync()
    test_save_opportunity_never_resets_dismissal_reason_on_resync()
    test_save_opportunity_concurrent_with_qualification_update_never_reverts_it()
    print("OK — todos os testes de persistência passaram")
