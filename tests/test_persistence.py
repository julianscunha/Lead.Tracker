"""Testes de integração de persistência (SQLite real via aiosqlite,
arquivo temporário — nunca o banco real do módulo)."""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import create_engine, init_db, make_session_factory
from core.models import Company, Opportunity, OpportunityStatus, Portfolio, SourceRef, Vendor
from core.opportunity_engine import CorrelationRule, evaluate_rules
from core.repository import (
    get_company, get_portfolio_by_company, list_companies, list_opportunities,
    list_vendors, save_company, save_opportunity, save_portfolio, save_vendor,
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


if __name__ == "__main__":
    test_company_round_trip_preserves_sources_and_timestamps()
    test_get_company_returns_none_when_not_found()
    test_save_company_twice_upserts_not_duplicates()
    test_portfolio_round_trip_by_company_id()
    test_end_to_end_portfolio_to_rule_engine_to_persisted_opportunity()
    print("OK — todos os testes de persistência passaram")
