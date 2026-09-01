"""Smoke tests de exportação PDF/Excel."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.dashboard_metrics import DashboardKPIs
from exports.excel import opportunities_excel
from exports.pdf import executive_pdf, opportunities_pdf
from exports.types import OpportunityExportRow

SAMPLE_ROWS = [
    OpportunityExportRow(
        company_name="Aurora Sistemas Ltda", is_customer=True, opportunity_score=0.92,
        financial_potential=48000.0, product="VDC365", service=None, priority="alta",
        sources=["salesforce", "website"],
    ),
    OpportunityExportRow(
        company_name="Bytemark Tecnologia", is_customer=False, opportunity_score=0.67,
        financial_potential=None, product=None, service="Assessment de DR", priority="média",
        sources=["manual"],
    ),
]

SAMPLE_KPIS = DashboardKPIs(
    opportunities_identified=2, customers_analyzed=1, prospects_analyzed=1,
    financial_potential_total=48000.0, product_opportunities=1, service_opportunities=1,
    top_vendor="Veeam", top_service="Assessment de DR",
)


def test_opportunities_pdf_generates_valid_pdf_bytes_with_accented_names():
    result = opportunities_pdf(SAMPLE_ROWS, filters_summary="todos", generated_at=datetime.now(timezone.utc))
    assert result.startswith(b"%PDF")
    assert len(result) > 100


def test_opportunities_pdf_never_crashes_on_characters_outside_latin1():
    rows = [OpportunityExportRow(
        company_name="Condomínio São José — Ação Ágil 🚀", is_customer=True, opportunity_score=0.5,
        financial_potential=1000.0, product="Não informado", service=None, priority="alta", sources=["manual"],
    )]
    result = opportunities_pdf(rows, filters_summary="—", generated_at=datetime.now(timezone.utc))
    assert result.startswith(b"%PDF")


def test_opportunities_pdf_handles_empty_rows_without_crashing():
    result = opportunities_pdf([], filters_summary="nenhum filtro", generated_at=datetime.now(timezone.utc))
    assert result.startswith(b"%PDF")


def test_executive_pdf_generates_valid_pdf_bytes():
    result = executive_pdf(
        SAMPLE_KPIS, top_opportunities=SAMPLE_ROWS, insights="Resumo de teste.",
        generated_at=datetime.now(timezone.utc), period_label="Setembro/2026",
        vendor_distribution=[("Veeam", 3), ("VMware", 1)],
        funnel_counts={"Detectadas": 4, "Qualificadas": 2},
    )
    assert result.startswith(b"%PDF")


def test_opportunities_excel_generates_valid_xlsx_bytes():
    result = opportunities_excel(SAMPLE_ROWS)
    assert result.startswith(b"PK")  # xlsx é um zip
    assert len(result) > 100


def test_opportunities_excel_handles_empty_rows():
    result = opportunities_excel([])
    assert result.startswith(b"PK")


if __name__ == "__main__":
    test_opportunities_pdf_generates_valid_pdf_bytes_with_accented_names()
    test_opportunities_pdf_never_crashes_on_characters_outside_latin1()
    test_opportunities_pdf_handles_empty_rows_without_crashing()
    test_executive_pdf_generates_valid_pdf_bytes()
    test_opportunities_excel_generates_valid_xlsx_bytes()
    test_opportunities_excel_handles_empty_rows()
    print("OK — todos os testes de exportação passaram")
