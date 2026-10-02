"""R11 — o perfil do CSV (segmento, região, representante) não é mais descartado quando a empresa já existe."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Company, SourceRef  # noqa: E402
from core.repository import list_audit_entries, list_companies, list_field_conflicts, save_company  # noqa: E402
from tests.test_routes_sync import _TempDb, _upload_csv  # noqa: E402


def _seed(db, **kw):
    company = Company(name="Aurora Sistemas", sources=[SourceRef(type="salesforce")], **kw)

    async def run():
        async with db.session_factory() as session:
            await save_company(session, company)
    asyncio.run(run())
    return company


def _state(db):
    async def run():
        async with db.session_factory() as session:
            company = (await list_companies(session))[0]
            return company, await list_field_conflicts(session), await list_audit_entries(session, company_id=company.id)
    return asyncio.run(run())


def test_csv_fills_empty_profile_fields_of_existing_company_instead_of_dropping_them():
    with _TempDb() as db:
        _seed(db)
        resp = _upload_csv("company_name,segment,region,rep_id\nAurora Sistemas,Médio porte,Sudeste,rep-1\n")
        assert resp.status_code == 200 and resp.json()["conflicts_opened"] == 0
        company, conflicts, _ = _state(db)
        assert (company.segment, company.region, company.rep_id) == ("Médio porte", "Sudeste", "rep-1")
        assert conflicts == [] and company.field_sources["segment"] == "csv"


def test_csv_value_that_differs_from_another_source_opens_conflict_and_keeps_current():
    with _TempDb() as db:
        _seed(db, rep_id="rep-1", segment="Grande")
        resp = _upload_csv("company_name,segment,rep_id\nAurora Sistemas,Pequeno,rep-2\n")
        assert resp.json()["conflicts_opened"] == 2
        company, conflicts, _ = _state(db)
        assert (company.rep_id, company.segment) == ("rep-1", "Grande")  # nada sobrescrito em silêncio
        assert {c.field for c in conflicts} == {"rep_id", "segment"}


def test_csv_reimport_of_its_own_value_refreshes_with_audit_and_blank_cells_never_erase():
    with _TempDb() as db:
        _upload_csv("company_name,segment\nNova Empresa,Pequeno\n")
        _upload_csv("company_name,segment\nNova Empresa,Médio\n")  # a própria planilha corrige o valor
        company, conflicts, audit = _state(db)
        assert company.segment == "Médio" and conflicts == []
        assert [(e.field, e.old_value, e.new_value, e.actor) for e in audit] == [("segment", "Pequeno", "Médio", "sync:csv")]
        _upload_csv("company_name,segment\nNova Empresa,\n")  # célula vazia não apaga
        assert _state(db)[0].segment == "Médio"


def test_csv_rep_ids_that_only_differ_by_punctuation_are_different_people():
    with _TempDb() as db:
        _seed(db, rep_id="rep-1")
        resp = _upload_csv("company_name,rep_id\nAurora Sistemas,rep1\n")
        assert resp.json()["conflicts_opened"] == 1
        assert _state(db)[0].rep_id == "rep-1"


def test_same_company_written_with_different_spelling_is_one_company():
    """Regressão da revisão: a planilha era agrupada pelo nome literal; "Acme" e "ACME" virariam
    duas entradas e a reconciliação da primeira se perderia."""
    with _TempDb() as db:
        _seed(db, rep_id="rep-1")
        resp = _upload_csv("company_name,rep_id,segment\nAurora Sistemas,rep-9,Médio\nAURORA SISTEMAS,rep-9,\n")
        assert resp.json()["companies_imported"] == 1
        company, conflicts, _ = _state(db)
        assert company.segment == "Médio" and company.rep_id == "rep-1"
        assert [c.field for c in conflicts] == ["rep_id"]


def test_geo_assigned_rep_has_a_real_source_and_resolving_legacy_keeps_current_value():
    from core.repository import resolve_field_conflict
    with _TempDb() as db:
        _seed(db, rep_id="rep-1")  # rep sem dono registrado numa empresa antiga
        _upload_csv("company_name,rep_id\nAurora Sistemas,rep-2\n")
        company, conflicts, _ = _state(db)
        assert conflicts[0].candidates[0].source == "salesforce"  # dono derivado, nunca um valor velho solto
        legacy = Company(name="Outra", sources=[SourceRef(type="salesforce"), SourceRef(type="csv")], rep_id="rep-1")

        async def run():
            async with db.session_factory() as session:
                from core.db_models import CompanyORM
                from core.repository import record_reconciliation
                from core.normalization import ConflictProposal
                await save_company(session, legacy)
                await record_reconciliation(
                    session, legacy.id, [], [ConflictProposal("rep_id", "rep-1", "legacy", "rep-7", "csv")], "csv",
                )
                conflict = [c for c in await list_field_conflicts(session) if c.company_id == legacy.id][0]
                # o valor guardado do "legacy" pode estar velho: escolher "legacy" mantém o valor ATUAL
                legacy_row = await session.get(CompanyORM, legacy.id)
                legacy_row.rep_id = "rep-1-atualizado"
                await session.commit()
                await resolve_field_conflict(session, conflict.id, "legacy")
                return (await list_companies(session))
        companies = asyncio.run(run())
        assert {c.name: c.rep_id for c in companies}["Outra"] == "rep-1-atualizado"
