"""Exportação em Excel — mesma regra: só dados já resolvidos, nunca segredo."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from exports.errors import wrap_export_errors
from exports.types import OpportunityExportRow

_HEADERS = ["Empresa", "Cliente", "Score", "Potencial", "Produto", "Serviço", "Prioridade", "Fontes"]


@wrap_export_errors
def opportunities_excel(rows: list[OpportunityExportRow]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Oportunidades"
    ws.append(_HEADERS)

    for row in rows:
        ws.append([
            row.company_name,
            "Cliente" if row.is_customer else "Prospect",
            row.opportunity_score,
            row.financial_potential,
            row.product,
            row.service,
            row.priority,
            ", ".join(row.sources),
        ])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
