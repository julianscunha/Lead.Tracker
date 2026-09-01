"""
Exportação em PDF.

Nunca recebe segredo/config — só dados já resolvidos pra exibição. Isso é
estrutural: as funções aqui não sabem nada sobre .env/AI_API_KEY/tokens,
então não há como vazar nada.
"""
from __future__ import annotations

from datetime import datetime

from fpdf import FPDF

from core.dashboard_metrics import DashboardKPIs
from exports.errors import wrap_export_errors
from exports.types import OpportunityExportRow

METHODOLOGY_SUMMARY = (
    "Oportunidades sao geradas por regras deterministicas de correlacao de portfolio "
    "(presenca/ausencia de produto ou servico), com evidencia obrigatoria. IA e complementar: "
    "interpreta e enriquece, nunca decide sozinha nem inventa produto fora do portfolio."
)


_LATIN1_REPLACEMENTS = {
    "—": "-", "–": "-",  # travessão/meia-risca
    "‘": "'", "’": "'", "“": '"', "”": '"',  # aspas curvas
    "…": "...",
}


def _pdf_safe(text: str) -> str:
    """A fonte core (Helvetica) só cobre latin-1. Nunca deixar um nome de
    empresa/produto real (travessão, aspas curvas, emoji, etc.) derrubar a
    exportação — troca o que reconhece, descarta o resto sem quebrar."""
    for char, replacement in _LATIN1_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _format_currency(value: float | None) -> str:
    if value is None:
        return "-"
    return f"R$ {value:,.0f}".replace(",", ".")


def _format_score(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


@wrap_export_errors
def opportunities_pdf(rows: list[OpportunityExportRow], filters_summary: str, generated_at: datetime) -> bytes:
    """PDF da tabela de Oportunidades — respeita filtros/ordenação já aplicados pelo chamador."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Lead.Tracker - Oportunidades", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Gerado em {generated_at.strftime('%d/%m/%Y %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Filtros: {_pdf_safe(filters_summary)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Total: {len(rows)} oportunidade(s)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    headers = ["Empresa", "Cliente", "Score", "Potencial", "Produto", "Servico", "Prioridade", "Fontes"]
    widths = [55, 20, 18, 28, 40, 40, 25, 40]

    pdf.set_font("Helvetica", "B", 9)
    for h, w in zip(headers, widths):
        pdf.cell(w, 8, h, border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for row in rows:
        pdf.cell(widths[0], 7, _pdf_safe(row.company_name)[:38], border=1)
        pdf.cell(widths[1], 7, "Cliente" if row.is_customer else "Prospect", border=1)
        pdf.cell(widths[2], 7, _format_score(row.opportunity_score), border=1)
        pdf.cell(widths[3], 7, _format_currency(row.financial_potential), border=1)
        pdf.cell(widths[4], 7, _pdf_safe(row.product or "-")[:26], border=1)
        pdf.cell(widths[5], 7, _pdf_safe(row.service or "-")[:26], border=1)
        pdf.cell(widths[6], 7, _pdf_safe(row.priority), border=1)
        pdf.cell(widths[7], 7, _pdf_safe(", ".join(row.sources))[:26], border=1)
        pdf.ln()

    return bytes(pdf.output())


@wrap_export_errors
def executive_pdf(
    kpis: DashboardKPIs,
    top_opportunities: list[OpportunityExportRow],
    insights: str,
    generated_at: datetime,
    period_label: str,
    vendor_distribution: list[tuple[str, int]],
    funnel_counts: dict[str, int],
) -> bytes:
    """
    PDF executivo. 'Graficos' viram tabelas de apoio aqui —
    ponytail: rasterizar SVG/gerar imagem de grafico pediria uma dependencia
    nova (matplotlib) so pra isso; se vier a ser pedido de verdade, trocar por
    imagem renderizada a partir do mesmo dado.
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "Lead.Tracker - Resumo Executivo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Periodo: {_pdf_safe(period_label)} | Gerado em {generated_at.strftime('%d/%m/%Y %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "KPIs", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    kpi_lines = [
        f"Oportunidades identificadas: {kpis.opportunities_identified}",
        f"Clientes analisados: {kpis.customers_analyzed}",
        f"Prospects analisados: {kpis.prospects_analyzed}",
        f"Potencial financeiro: {_format_currency(kpis.financial_potential_total)}",
        f"Oportunidades de produto: {kpis.product_opportunities}",
        f"Oportunidades de servico: {kpis.service_opportunities}",
        f"Fabricante principal: {_pdf_safe(kpis.top_vendor) if kpis.top_vendor else '-'}",
        f"Servico principal: {_pdf_safe(kpis.top_service) if kpis.top_service else '-'}",
    ]
    for line in kpi_lines:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Distribuicao por fabricante", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for name, count in vendor_distribution:
        pdf.cell(0, 6, f"{_pdf_safe(name)}: {count}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Funil", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for stage, count in funnel_counts.items():
        pdf.cell(0, 6, f"{_pdf_safe(stage)}: {count}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Principais oportunidades", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for row in top_opportunities:
        pdf.cell(0, 6, f"{_pdf_safe(row.company_name)} - score {_format_score(row.opportunity_score)} - {_format_currency(row.financial_potential)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Insights", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _pdf_safe(insights))
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Metodologia", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, METHODOLOGY_SUMMARY)

    return bytes(pdf.output())
