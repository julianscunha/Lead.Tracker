"""
Exportação em PDF.

Nunca recebe segredo/config — só dados já resolvidos pra exibição. Isso é
estrutural: as funções aqui não sabem nada sobre .env/AI_API_KEY/tokens,
então não há como vazar nada.
"""
from __future__ import annotations

from datetime import datetime

from fpdf import FPDF
from fpdf.enums import WrapMode

from core.business_case import NOT_ASSESSED, BusinessCase, truncate
from core.dashboard_metrics import DashboardKPIs
from exports.errors import ExportError, wrap_export_errors
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

    headers = ["Empresa", "Cliente", "Score", "Valor tipico", "Produto", "Servico", "Prioridade", "Fontes"]
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
        f"Valor tipico informado: {_format_currency(kpis.financial_potential_total)}",
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


# --- Business case (A4 retrato, exatamente 1 página) ---------------------------------
# Síncrona e CPU-bound (medição de linhas do fpdf2): a rota chama via `run_in_threadpool`
# (backend/routes_exports.py) para não bloquear o event loop.
_M, _W = 15, 180            # margem e largura útil (mm)
_BODY_LIMIT = 297 - 40      # os 40 mm finais ficam reservados ao rodapé
_FOOTER_Y = 270
_FOOTER_LINE_H = 3.5
_FOOTER_MAX_LINES = 4
_FOOTER_MAX_CHARS = 600
_SECTION_MAX_CHARS = 1800   # a página comporta ~7 mil caracteres a 7,5 pt
_SIZES = (9.5, 9, 8.5, 8, 7.5)
_SHRINK = 0.95              # folga ao cortar texto por proporção
_ITEM_MAX_CHARS = 120
_LEGEND_MAX_CHARS = 300
_SCORE_BOX_W, _SCORE_BOX_H = 45, 13
_SCORE_LABEL_W = _SCORE_BOX_W - 4
_SCORE_LABEL_MAX = 30
_RESUMIDO = " Texto resumido."


def _nlines(pdf: FPDF, w: float, h: float, text: str) -> int:
    # WORD: quebra por palavra e, só se uma palavra passar da largura, por caractere (fpdf2 >= 2.7).
    lines = pdf.multi_cell(w, h, text, dry_run=True, output="LINES", wrapmode=WrapMode.WORD)
    return max(len(lines), 1)


def _clip(pdf: FPDF, w: float, h: float, text: str, max_lines: int, suffix: str = "") -> str:
    """Corta `text` (com `suffix` fixo ao final) até caber em `max_lines`; fonte já definida."""
    n = _nlines(pdf, w, h, text + suffix)
    while n > max_lines and len(text) > 1:
        text = text[: max(int(len(text) * max_lines / n * _SHRINK) - 3, 1)].rstrip() + "..."
        n = _nlines(pdf, w, h, text + suffix)
    return text + suffix


def _bc_flow(pdf: FPDF, t: dict, secoes: list, size: float, draw: bool) -> float:
    """Mesmo caminho para medir e desenhar: devolve o y final do corpo."""
    lh = 4.6 * size / 9.5
    y = 15.0
    memo = t.setdefault("_memo", {})

    def text(font_style: str, fsize: float, h: float, txt: str, gray: int = 0) -> None:
        nonlocal y
        pdf.set_font("Helvetica", font_style, fsize)
        key = (font_style, fsize, h, txt)  # a medição é cara: reaproveita entre tamanhos/voltas
        if key not in memo:
            memo[key] = _nlines(pdf, _W, h, txt)
        n = memo[key]
        if draw:
            pdf.set_text_color(gray)
            pdf.set_xy(_M, y)
            pdf.multi_cell(_W, h, txt, align="L", wrapmode=WrapMode.WORD)  # L: sem buracos antes de token longo
        y += n * h

    text("", 8, 4, t["marca"], 80)
    text("B", 16, 7, t["empresa"])
    text("", 10, 5, t["item_data"])
    y += 1
    if draw:
        pdf.set_line_width(0.4)
        pdf.line(_M, y, _M + _W, y)
    y += 3
    for i, (label, band) in enumerate(t["scores"]):
        x = _M + i * _SCORE_BOX_W
        if draw:
            pdf.set_line_width(0.3)
            if band == t["na"]:
                pdf.set_dash_pattern(dash=1, gap=1)
            pdf.rect(x, y, _SCORE_BOX_W, _SCORE_BOX_H)
            pdf.set_dash_pattern()
            pdf.set_xy(x + 2, y + 1.5)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(90)
            pdf.cell(_SCORE_LABEL_W, 3, label)
            pdf.set_xy(x + 2, y + 6)
            pdf.set_font("Helvetica", "" if band == t["na"] else "B", 11)
            pdf.set_text_color(90 if band == t["na"] else 0)
            pdf.cell(_SCORE_LABEL_W, 5, band)
    y += _SCORE_BOX_H + 1.5
    text("I", 7.5, 4, t["legenda"], 90)
    y += 3
    for title, body, style, gray in secoes:
        text("B", 10, 5, title)
        if draw:
            pdf.set_line_width(0.15)
            pdf.line(_M, y, _M + _W, y)
        y += 1.5
        text(style, size, lh, body, gray)
        y += 4
    return y


def _shrink_to_fit(pdf: FPDF, t: dict, titles: list, bodies: list, styles: list) -> tuple[float, list, bool]:
    """Escolhe a maior fonte que cabe; no piso, resume a seção mais longa por proporção.
    Devolve (fonte, corpos, houve_corte)."""
    resumido = any(len(b) > _SECTION_MAX_CHARS for b in bodies)
    bodies = [b if len(b) <= _SECTION_MAX_CHARS else b[:_SECTION_MAX_CHARS].rstrip() + "..." for b in bodies]

    def secoes() -> list:
        return [(ti, b, st[0], st[1]) for ti, b, st in zip(titles, bodies, styles)]

    def altura(size: float) -> float:
        return _bc_flow(pdf, t, secoes(), size, False)

    while True:
        h_min = altura(_SIZES[-1])  # só no piso de fonte se decide cortar texto
        if h_min <= _BODY_LIMIT:
            return next(sz for sz in _SIZES if altura(sz) <= _BODY_LIMIT), bodies, resumido
        fator = min(_BODY_LIMIT / h_min * _SHRINK, _SHRINK)
        i = max(range(len(bodies)), key=lambda k: len(bodies[k]))
        if len(bodies[i]) <= 3:
            raise ExportError(
                "O texto deste business case é longo demais para caber em uma página.",
                "Reduza as evidências ou a descrição do produto/serviço e tente novamente.",
            )
        palavras = len(bodies[i].split())
        if palavras > 1:
            bodies[i] = _pdf_safe(truncate(bodies[i], max(int(palavras * fator), 1)))
        else:
            bodies[i] = bodies[i][: int(len(bodies[i]) * fator)].rstrip() + "..."
        resumido = True


@wrap_export_errors
def business_case_pdf(doc: BusinessCase, generated_at: datetime) -> bytes:
    """Business case de 1 página: reduz a fonte (até 7,5 pt), depois resume o texto; nunca cria 2ª página."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_margins(_M, _M, _M)
    pdf.set_creation_date(generated_at)
    pdf.set_title(_pdf_safe(f"Business case - {doc.empresa} - {doc.item}"))
    pdf.set_author("Lead.Tracker")
    pdf.set_subject(_pdf_safe("Rascunho para revisão do vendedor"))
    pdf.set_lang("pt-BR")
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    empresa = _clip(pdf, _W, 7, _pdf_safe(doc.empresa), 2)
    pdf.set_font("Helvetica", "", 10)
    item = _pdf_safe(doc.item)[:_ITEM_MAX_CHARS]
    item_data = _clip(pdf, _W, 5, item, 2, _pdf_safe(f" - {generated_at:%d/%m/%Y %H:%M}"))
    pdf.set_font("Helvetica", "I", 7.5)
    legenda = _clip(pdf, _W, 4, _pdf_safe(doc.legenda_scores)[:_LEGEND_MAX_CHARS], 2)

    sev_style = {"critico": ("B", 0), "alto": ("B", 0), "nao_avaliado": ("I", 90)}.get(doc.severidade, ("", 0))
    bodies = [_pdf_safe(x) for x in (doc.situacao, doc.gap, doc.custo, doc.estado_futuro)]
    titles = [_pdf_safe(x) for x in ("Situação atual", "Gap (lacuna)", "Custo de não agir", "Estado futuro")]
    styles = [("", 0), ("", 0), sev_style, ("", 0)]
    t = {
        "marca": "Lead.Tracker - Business case", "empresa": empresa, "item_data": item_data,
        "scores": [(_pdf_safe(a)[:_SCORE_LABEL_MAX], _pdf_safe(b)) for a, b in doc.scores[:4]],
        "na": _pdf_safe(NOT_ASSESSED), "legenda": legenda,
    }

    size, bodies, resumido = _shrink_to_fit(pdf, t, titles, bodies, styles)
    _bc_flow(pdf, t, [(ti, b, st[0], st[1]) for ti, b, st in zip(titles, bodies, styles)], size, True)

    rodape = _pdf_safe(doc.rodape)[:_FOOTER_MAX_CHARS]
    cauda = _RESUMIDO if resumido else ""
    pdf.set_font("Helvetica", "", 7.5)
    n = _nlines(pdf, _W, _FOOTER_LINE_H, rodape + cauda)
    while n > _FOOTER_MAX_LINES and len(rodape.split()) > 1:
        rodape = _pdf_safe(truncate(rodape, max(int(len(rodape.split()) * _FOOTER_MAX_LINES / n * _SHRINK), 1)))
        n = _nlines(pdf, _W, _FOOTER_LINE_H, rodape + cauda)
    pdf.set_text_color(60)
    pdf.set_xy(_M, _FOOTER_Y)
    pdf.multi_cell(_W, _FOOTER_LINE_H, rodape + cauda, align="L", wrapmode=WrapMode.WORD)
    return bytes(pdf.output())
