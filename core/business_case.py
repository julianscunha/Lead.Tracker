"""Business case por oportunidade — montagem determinística (sem IA, sem I/O, sem R$).

Função pura: Opportunity + Company + item do portfólio -> documento de 4 seções
(situação, gap, custo de não agir, estado futuro) com cabeçalho e rodapé.
Reaproveita `compute_severity_band`; nenhum limiar de severidade novo aqui.

Data da evidência: `Opportunity.synced_at` (data de sincronização, não a data do
fato no CRM) — rotulada como tal. `today` é parâmetro explícito para manter a
função pura e testável.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.errors import DomainError, ErrorCategory
from core.models import Company, Opportunity, Product, Service
from core.opportunity_engine import compute_severity_band

# Faixas dos scores: terços iguais da escala 0–1 (default de CorrelationRule;
# o modelo não impõe a escala). Ajustáveis.
SCORE_LOW_MAX = 0.33
SCORE_MID_MAX = 0.66
NOT_ASSESSED = "Não avaliado"

# (campo de Opportunity, rótulo para o vendedor) — ordem fixa, nunca fundidos.
SCORE_LABELS: tuple[tuple[str, str], ...] = (
    ("opportunity_score", "Aderência ao portfólio"),
    ("financial_potential", "Porte estimado da conta"),
    ("strategic_score", "Relevância estratégica"),
    ("confidence_score", "Solidez das evidências"),
)
SCORES_LEGEND = "Dimensões independentes: não são somadas nem combinadas."

SEVERITY_LABELS = {
    "baixo": "Baixo", "medio": "Médio", "alto": "Alto", "critico": "Crítico", "nao_avaliado": NOT_ASSESSED,
}

# Envelhecimento da evidência (dias desde a sincronização).
AGING_CONFIRM_DAYS = 30
AGING_STALE_DAYS = 90

# Limites de palavras por seção (truncamento determinístico).
MAX_WORDS_SITUACAO = 70
MAX_WORDS_GAP = 70
MAX_WORDS_CUSTO = 60
MAX_WORDS_ESTADO_FUTURO = 60
MAX_WORDS_RODAPE = 40
MAX_GAP_EVIDENCES = 3

DRAFT_MARK = "rascunho para revisão do vendedor; não enviado"


@dataclass(frozen=True)
class BusinessCase:
    empresa: str
    item: str
    data: date
    scores: tuple[tuple[str, str], ...]  # (rótulo, faixa) — nunca o número cru
    legenda_scores: str
    situacao: str
    gap: str
    custo: str
    estado_futuro: str
    rodape: str
    severidade: str  # nao_avaliado | baixo | medio | alto | critico
    tom_condicional: bool  # confiança Baixa -> prosa com verbos condicionais

    def texto_completo(self) -> str:
        partes = [self.empresa, self.item, self.legenda_scores, self.situacao, self.gap, self.custo, self.estado_futuro, self.rodape]
        partes += [f"{rotulo}: {faixa}" for rotulo, faixa in self.scores]
        return "\n".join(partes)


def score_band(value: float | None) -> str:
    # Escala 0–1 é default CorrelationRule; não imposta pelo modelo — ajustável em SCORE_LOW_MAX/MID_MAX.
    if value is None or value != value:  # value != value detects NaN
        return NOT_ASSESSED
    if value <= SCORE_LOW_MAX:
        return "Baixa"
    return "Média" if value <= SCORE_MID_MAX else "Alta"


def truncate(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + "…"


def fit(body: str, fixed_tail: str, max_words: int) -> str:
    """Trunca só `body`, preservando `fixed_tail` (avisos que não podem ser cortados)."""
    budget = max(max_words - len(fixed_tail.split()), 1)
    return f"{truncate(body, budget)} {fixed_tail}".strip()


def _clean(text: str) -> str:
    """Remove pontuação final (`.`/`;`) e espaços, para montar listas e rótulos com um único ponto."""
    return text.strip().rstrip(".; ").strip()


def aging_text(synced: date, today: date) -> str:
    days = (today - synced).days
    text = f"Dado sincronizado em {synced:%d/%m/%Y} (a data do fato no CRM pode ser anterior)."
    if days > AGING_STALE_DAYS:
        text += f" Dado antigo ({days} dias): reconfirmar. Confirme com o cliente antes de usar."
    elif days > AGING_CONFIRM_DAYS:
        text += f" Há {days} dias: confirme com o cliente antes de usar."
    return text


def assemble_business_case(opp: Opportunity, company: Company, item: Product | Service, today: date) -> BusinessCase:
    evidence = [c for c in (_clean(e) for e in opp.evidence if e) if c]
    if not evidence:
        raise DomainError(
            ErrorCategory.INVALID_DATA,
            "Não foi possível gerar o business case: faltam evidências para esta oportunidade.",
            "Sincronize os dados ou revise a oportunidade antes de exportar.",
        )

    scores = tuple((label, score_band(getattr(opp, field))) for field, label in SCORE_LABELS)
    solidez = score_band(opp.confidence_score)
    tom_condicional = solidez == "Baixa"

    name = f"{company.name} (cliente)" if company.is_customer else company.name
    situacao = fit(f"{name}. Evidências: {'; '.join(evidence)}.", aging_text(opp.synced_at.date(), today), MAX_WORDS_SITUACAO)

    rotulo = "Possível motivo (confiança baixa)" if tom_condicional else "Motivo principal"
    just = _clean(opp.justification or "")
    motivo = f"{rotulo}: {just}." if just else ""
    gap = truncate(f"{motivo} Fatos: {'; '.join(evidence[:MAX_GAP_EVIDENCES])}.".strip(), MAX_WORDS_GAP)

    severidade = compute_severity_band(opp.scope_note, opp.criticality)
    custo = truncate(
        f"Severidade de não agir: {SEVERITY_LABELS[severidade]}. "
        "Banda qualitativa avaliada pelo vendedor (abrangência e criticidade), não um valor financeiro.",
        MAX_WORDS_CUSTO,
    )

    desc = (item.description or "").strip()
    estado_futuro = truncate(desc, MAX_WORDS_ESTADO_FUTURO) if desc else item.name

    fontes = ", ".join(dict.fromkeys(s.type for s in opp.sources)) or "não informadas"
    cauda = f"Solidez das evidências: {solidez}. Gerado em {today:%d/%m/%Y}; {DRAFT_MARK}."
    rodape = fit(f"Fontes: {fontes}.", cauda, MAX_WORDS_RODAPE)

    return BusinessCase(
        empresa=company.name, item=item.name, data=today, scores=scores, legenda_scores=SCORES_LEGEND,
        situacao=situacao, gap=gap, custo=custo, estado_futuro=estado_futuro, rodape=rodape,
        severidade=severidade, tom_condicional=tom_condicional,
    )
