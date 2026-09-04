"""
Motor de Oportunidades — regras determinísticas.

Regras vêm antes da IA (CLAUDE.md 'Deterministic rules come before AI').
Sem IA aqui. `financial_potential` e `strategic_score` ficam `None`: não há
dado real pra sustentá-los ainda, e nunca inventamos número — núcleo genérico,
sem depender de informação específica de uma empresa ou fabricante.

Regras não são hardcoded no core — são dados, configuráveis pelo portfólio
(fabricante/produto específico é decisão do usuário, não do código).

`CorrelationRule`/`RuleError` moraram aqui até a Fase C — agora vivem em
core/models.py (regra virou modelo de domínio persistido). Reexportados
daqui pra quem já importava deste módulo continuar funcionando.
"""
from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from core.models import (
    CorrelationRule, Opportunity, OpportunityStatus, Portfolio, Product, RuleError, Service, SourceRef,
)

__all__ = ["CorrelationRule", "RuleError", "evaluate_rules"]


def _deterministic_opportunity_id(company_id: str, rule_id: str, evidence: list[str]) -> str:
    """ID estável a partir de (empresa, regra, evidência) — nunca aleatório.
    Sem isso, rodar sync duas vezes pra uma empresa cujo portfólio não
    mudou persistiria uma Opportunity NOVA a cada vez (upsert por id só
    evita duplicata se o id for o mesmo pro mesmo fato). `evidence` entra
    na chave porque uma regra de relação pode disparar mais de uma vez por
    empresa (um produto por vez), cada disparo precisa de id próprio."""
    key = f"{company_id}:{rule_id}:{'|'.join(sorted(evidence))}"
    return str(uuid5(NAMESPACE_URL, key))


def _portfolio_items(portfolio: Portfolio) -> set[str]:
    return set(portfolio.vendor_ids) | set(portfolio.product_ids) | set(portfolio.service_ids)


def _categories_present(items: set[str], products: list[Product], services: list[Service]) -> set[str]:
    categories = {p.category for p in products if p.id in items and p.category}
    categories |= {s.category for s in services if s.id in items and s.category}
    return categories


def _build_opportunity(
    rule: CorrelationRule, portfolio: Portfolio, evidence: list[str], risk_flag: str | None = None,
) -> Opportunity:
    return Opportunity(
        id=_deterministic_opportunity_id(portfolio.company_id, rule.id, evidence),
        company_id=portfolio.company_id,
        type=rule.opportunity_type,
        opportunity_score=rule.opportunity_score,
        financial_potential=None,
        strategic_score=None,
        confidence_score=rule.confidence_score,
        evidence=evidence,
        justification=rule.justification,
        sources=[SourceRef(type="rule_engine", confidence=rule.confidence_score)],
        status=OpportunityStatus.DETECTED,
        risk_flag=risk_flag,
    )


def _evaluate_simple_rule(rule: CorrelationRule, items: set[str]) -> Opportunity | None:
    requires_met = all(item in items for item in rule.requires)
    absent_met = not any(item in items for item in rule.absent)
    return None if not (requires_met and absent_met) else rule


def _evaluate_category_rule(rule: CorrelationRule, categories: set[str]) -> list[str] | None:
    requires_met = all(cat in categories for cat in rule.requires_category)
    absent_met = not any(cat in categories for cat in rule.absent_category)
    if not (requires_met and absent_met):
        return None
    return sorted(categories & set(rule.requires_category))


def _evaluate_relation_rule(
    rule: CorrelationRule, portfolio: Portfolio, items: set[str], products: list[Product],
) -> list[Opportunity]:
    """`prerequisite`: produto presente sem o serviço-pré-requisito vira
    `risk_flag` (nunca uma oportunidade de venda fake). `substitute`:
    produto e seu substituto ambos presentes vira oportunidade de
    consolidação (via `rule.opportunity_type`, convenção `"consolidation"`)."""
    results: list[Opportunity] = []
    for product in products:
        if product.id not in items:
            continue
        for relation in product.related_services:
            if relation.relation_type != rule.relation_type:
                continue
            service_present = relation.service_id in items
            if rule.relation_type == "prerequisite" and not service_present:
                results.append(_build_opportunity(
                    rule, portfolio, evidence=[product.id],
                    risk_flag=f"{product.id} vendido sem o pré-requisito {relation.service_id}.",
                ))
            elif rule.relation_type == "substitute" and service_present:
                results.append(_build_opportunity(rule, portfolio, evidence=[product.id, relation.service_id]))
    return results


def evaluate_rules(
    portfolio: Portfolio,
    rules: list[CorrelationRule],
    products: list[Product] | None = None,
    services: list[Service] | None = None,
) -> list[Opportunity]:
    """
    Avalia cada regra ativa contra o portfólio da empresa. Uma regra usa só
    um dos 3 mecanismos (checado em `CorrelationRule`, nunca combinados):
    presença/ausência simples, categoria, ou relação tipada (precisa do
    catálogo — `products`/`services` — pra resolver categoria/relação;
    omitidos, regra de categoria/relação simplesmente não encontra nada,
    retrocompatível com quem só usa regra simples).
    """
    products = products or []
    services = services or []
    items = _portfolio_items(portfolio)
    categories = _categories_present(items, products, services)
    opportunities: list[Opportunity] = []

    for rule in rules:
        if not rule.active:
            continue

        if rule.relation_type:
            opportunities.extend(_evaluate_relation_rule(rule, portfolio, items, products))
        elif rule.requires_category or rule.absent_category:
            evidence = _evaluate_category_rule(rule, categories)
            if evidence is not None:
                opportunities.append(_build_opportunity(rule, portfolio, evidence=evidence))
        else:
            if _evaluate_simple_rule(rule, items) is not None:
                opportunities.append(_build_opportunity(rule, portfolio, evidence=list(rule.requires)))

    return opportunities
