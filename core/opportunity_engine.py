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

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from core.models import (
    Company, CompanySignal, CorrelationRule, Opportunity, OpportunityStatus, Portfolio, Product,
    RuleError, Service, SourceRef,
)

_WARM_WINDOW_DAYS = 120
_LUKEWARM_WINDOW_DAYS = 270
_LUKEWARM_MULTIPLIER = 0.85
_COLD_MULTIPLIER = 0.5

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


def _portfolio_items(portfolio: Portfolio, signals: list[CompanySignal]) -> set[str]:
    """Conjunto de "itens presentes" pra regra simples avaliar — portfólio
    (vendor/product/service) + signal_type de todo CompanySignal ABERTO
    (sinal resolvido/descartado nunca dispara regra: já foi tratado).
    Sinal entra aqui, não como mecanismo novo — "só 3 tipos de regra"."""
    items = set(portfolio.vendor_ids) | set(portfolio.product_ids) | set(portfolio.service_ids)
    items |= {s.signal_type for s in signals if s.status == "open"}
    return items


def _categories_present(items: set[str], products: list[Product], services: list[Service]) -> set[str]:
    categories = {p.category for p in products if p.id in items and p.category}
    categories |= {s.category for s in services if s.id in items and s.category}
    return categories


def _fact_description(rule: CorrelationRule, evidence: list[str]) -> str:
    """`evidence` fica vazio numa regra só-de-ausência (`absent`/
    `absent_category` sem `requires`, mecanismo válido pra `CorrelationRule`)
    — sem isso o [FATO] sairia em branco, exatamente o log técnico cru que
    o princípio 2 proíbe."""
    if evidence:
        return ", ".join(evidence)
    ausencia = rule.absent or rule.absent_category
    return f"ausência de {', '.join(ausencia)}" if ausencia else "condição da regra satisfeita"


def _evidence_summary(
    rule: CorrelationRule, evidence: list[str], source_type: str, risk_flag: str | None, synced_at: datetime,
) -> str:
    """Princípio 2 do roadmap: fato + implicação de negócio + fonte + data,
    nunca um log técnico cru. `[RISCO]` quando a regra sinaliza risco
    técnico (prerequisite), `[OPORTUNIDADE]` nos demais casos."""
    label = "RISCO" if risk_flag else "OPORTUNIDADE"
    return (
        f"[FATO] {_fact_description(rule, evidence)} → [{label}] {rule.justification} → "
        f"[FONTE] {source_type}, sincronizado em {synced_at:%d/%m/%Y}"
    )


def _warmth_multiplier(company: Company | None) -> float:
    """Fase C, Fatia 4a (corrigido após revisão com Pipeline Analyst — ciclo
    de venda B2B de infraestrutura roda 90-180+ dias, corte binário em 90
    dias tratava conta só no ritmo normal do ciclo como "esfriada" e
    igualava "91 dias sem atividade" a "700 dias"). 3 níveis: quente
    (≤120 dias) mantém confiança cheia; morno (121-270 dias) reduz 15%;
    muito frio (>270 dias OU nunca registrado — ausência já é o sinal,
    nunca um terceiro estado "desconhecido") reduz 50%. `company` não
    passado (retrocompat) não penaliza.

    `last_activity_at` sempre chega UTC-aware por quem já persistiu/mapeou
    (core/repository.py `_ensure_utc`, providers/salesforce.py), mas essa
    função é chamada com um `Company` vindo de fora — reanexa UTC se algum
    dia vier naive, em vez de deixar `TypeError` explodir cru até o sync
    (CLAUDE.md: nunca vazar exceção técnica pro usuário)."""
    if company is None or company.last_activity_at is None:
        return 1.0 if company is None else _COLD_MULTIPLIER
    last_activity_at = company.last_activity_at
    if last_activity_at.tzinfo is None:
        last_activity_at = last_activity_at.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - last_activity_at).days
    if age_days <= _WARM_WINDOW_DAYS:
        return 1.0
    return _LUKEWARM_MULTIPLIER if age_days <= _LUKEWARM_WINDOW_DAYS else _COLD_MULTIPLIER


def _build_opportunity(
    rule: CorrelationRule, portfolio: Portfolio, evidence: list[str],
    risk_flag: str | None = None, company: Company | None = None,
) -> Opportunity:
    source_type = "rule_engine"
    synced_at = datetime.now(timezone.utc)
    confidence_score = rule.confidence_score * _warmth_multiplier(company)
    return Opportunity(
        id=_deterministic_opportunity_id(portfolio.company_id, rule.id, evidence),
        company_id=portfolio.company_id,
        type=rule.opportunity_type,
        opportunity_score=rule.opportunity_score,
        financial_potential=None,
        strategic_score=None,
        confidence_score=confidence_score,
        evidence=evidence,
        justification=rule.justification,
        sources=[SourceRef(type=source_type, confidence=rule.confidence_score)],
        status=OpportunityStatus.DETECTED,
        risk_flag=risk_flag,
        evidence_summary=_evidence_summary(rule, evidence, source_type, risk_flag, synced_at),
        discovery_prompt=rule.discovery_prompt,
        synced_at=synced_at,
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
    company: Company | None,
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
                    rule, portfolio, evidence=[product.id], company=company,
                    risk_flag=f"{product.id} vendido sem o pré-requisito {relation.service_id}.",
                ))
            elif rule.relation_type == "substitute" and service_present:
                results.append(_build_opportunity(
                    rule, portfolio, evidence=[product.id, relation.service_id], company=company,
                ))
    return results


def evaluate_rules(
    portfolio: Portfolio,
    rules: list[CorrelationRule],
    products: list[Product] | None = None,
    services: list[Service] | None = None,
    signals: list[CompanySignal] | None = None,
    company: Company | None = None,
) -> list[Opportunity]:
    """
    Avalia cada regra ativa contra o portfólio da empresa. Uma regra usa só
    um dos 3 mecanismos (checado em `CorrelationRule`, nunca combinados):
    presença/ausência simples, categoria, ou relação tipada (precisa do
    catálogo — `products`/`services` — pra resolver categoria/relação;
    omitidos, regra de categoria/relação simplesmente não encontra nada,
    retrocompatível com quem só usa regra simples). `signals` (sinal de
    expansão/risco, Fase B) entra como item a mais na regra simples —
    `requires=["renewal_upcoming"]` dispara se a empresa tiver um
    `CompanySignal` aberto desse tipo, mesmo mecanismo de sempre. `company`
    (Fase C, Fatia 4a) alimenta o multiplicador de `confidence_score` por
    recência de atividade — omitido (retrocompat) não penaliza.
    """
    products = products or []
    services = services or []
    signals = signals or []
    items = _portfolio_items(portfolio, signals)
    categories = _categories_present(items, products, services)
    opportunities: list[Opportunity] = []

    for rule in rules:
        if not rule.active:
            continue

        if rule.relation_type:
            opportunities.extend(_evaluate_relation_rule(rule, portfolio, items, products, company))
        elif rule.requires_category or rule.absent_category:
            evidence = _evaluate_category_rule(rule, categories)
            if evidence is not None:
                opportunities.append(_build_opportunity(rule, portfolio, evidence=evidence, company=company))
        else:
            if _evaluate_simple_rule(rule, items) is not None:
                opportunities.append(_build_opportunity(
                    rule, portfolio, evidence=list(rule.requires), company=company,
                ))

    return opportunities
