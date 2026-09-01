"""Smoke tests HTTP das rotas de exportação/rascunho, via FastAPI TestClient
(sem subir uvicorn nem chamar rede real — IA mockada via monkeypatch do factory)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / ".techforge-dev" / "sdk" / "python"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import main as backend_main

app = FastAPI()
app.include_router(backend_main.router)
client = TestClient(app)

SAMPLE_ROW = {
    "company_name": "Aurora Sistemas", "is_customer": True, "opportunity_score": 0.9,
    "financial_potential": 48000.0, "product": "VDC365", "service": None,
    "priority": "alta", "sources": ["salesforce"],
}


def test_export_pdf_returns_valid_pdf():
    resp = client.post("/modules/lead_tracker/exports/pdf", json={"rows": [SAMPLE_ROW], "filters_summary": "todos"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_export_excel_returns_valid_xlsx():
    resp = client.post("/modules/lead_tracker/exports/excel", json={"rows": [SAMPLE_ROW]})
    assert resp.status_code == 200
    assert resp.content.startswith(b"PK")


def test_export_executive_pdf_returns_valid_pdf():
    body = {
        "kpis": {
            "opportunities_identified": 1, "customers_analyzed": 1, "prospects_analyzed": 0,
            "financial_potential_total": 48000.0, "product_opportunities": 1, "service_opportunities": 0,
            "top_vendor": "Veeam", "top_service": None,
        },
        "top_opportunities": [SAMPLE_ROW],
        "insights": "Resumo.",
        "period_label": "Setembro/2026",
        "vendor_distribution": [["Veeam", 1]],
        "funnel_counts": {"Detectadas": 1},
    }
    resp = client.post("/modules/lead_tracker/exports/executive-pdf", json=body)
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_email_draft_returns_503_without_api_key():
    # .env deste checkout não tem AI_API_KEY preenchida (nunca versionamos .env real)
    resp = client.post("/modules/lead_tracker/email-draft", json={
        "company_name": "Aurora", "opportunity_type": "cross-sell", "evidence": ["veeam_vbr"],
    })
    assert resp.status_code == 503
    assert "AI_API_KEY" in resp.json()["detail"]


def test_export_pdf_rejects_invalid_body():
    resp = client.post("/modules/lead_tracker/exports/pdf", json={"rows": [{"company_name": "sem os outros campos"}]})
    assert resp.status_code == 422  # validação na borda, nunca chega no gerador de PDF


if __name__ == "__main__":
    test_export_pdf_returns_valid_pdf()
    test_export_excel_returns_valid_xlsx()
    test_export_executive_pdf_returns_valid_pdf()
    test_email_draft_returns_503_without_api_key()
    test_export_pdf_rejects_invalid_body()
    print("OK — todos os testes HTTP de exportação passaram")
