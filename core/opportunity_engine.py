"""
Motor de Oportunidades — regras determinísticas.

Regras vêm antes da IA (CLAUDE.md 'Deterministic rules come before AI').
Sem IA aqui. `financial_potential` e `strategic_score` ficam `None`: não há
dado real pra sustentá-los ainda, e nunca inventamos número — núcleo genérico,
sem depender de informação específica de uma empresa ou fabricante.

Regras não são hardcoded no core — são dados, configuráveis pelo portfólio
(fabricante/produto específico é decisão do usuário, não do código).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.models import Opportunity, OpportunityStatus, Portfolio, SourceRef


class RuleError(Exception):
    """Regra de correlação mal definida (ex.: sem 'requires')."""


@dataclass
class CorrelationRule:
    """
    Ex.: Veeam VBR presente + M365 presente + VDC365 ausente => Oportunidade VDC365
    (requires=["veeam_vbr", "m365"], absent=["vdc365"], opportunity_type="cross-sell").
    """
    id: str
    opportunity_type: str
    requires: list[str]
    justification: str
    absent: list[str] = field(default_factory=list)
    opportunity_score: float = 1.0
    confidence_score: float = 1.0

    def __post_init__(self) -> None:
        if not self.requires:
            raise RuleError(f"regra '{self.id}': 'requires' não pode ser vazio — oportunidade sem evidência")


def _portfolio_items(portfolio: Portfolio) -> set[str]:
    return set(portfolio.vendor_ids) | set(portfolio.product_ids) | set(portfolio.service_ids)


def evaluate_rules(portfolio: Portfolio, rules: list[CorrelationRule]) -> list[Opportunity]:
    """
    Avalia cada regra contra o portfólio da empresa. Gera uma Opportunity só
    quando todos os itens de `requires` estão presentes e nenhum de `absent`
    está presente. A evidência (motivo) é sempre os itens que confirmaram a regra.
    """
    items = _portfolio_items(portfolio)
    opportunities: list[Opportunity] = []

    for rule in rules:
        requires_met = all(item in items for item in rule.requires)
        absent_met = not any(item in items for item in rule.absent)
        if not (requires_met and absent_met):
            continue

        opportunities.append(Opportunity(
            company_id=portfolio.company_id,
            type=rule.opportunity_type,
            opportunity_score=rule.opportunity_score,
            financial_potential=None,
            strategic_score=None,
            confidence_score=rule.confidence_score,
            evidence=list(rule.requires),
            justification=rule.justification,
            sources=[SourceRef(type="rule_engine", confidence=rule.confidence_score)],
            status=OpportunityStatus.DETECTED,
        ))

    return opportunities
