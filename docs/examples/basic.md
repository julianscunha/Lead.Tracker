# Exemplo básico — detectar uma oportunidade

Fluxo mínimo, sem IA e sem provider externo: monta um portfólio, roda o
motor de regras determinístico, recebe uma oportunidade com evidência.

```python
from core.models import Portfolio
from core.opportunity_engine import CorrelationRule, evaluate_rules

portfolio = Portfolio(company_id="empresa-fictícia", product_ids=["veeam_vbr", "m365"])

rule = CorrelationRule(
    id="veeam_m365_sem_vdc365",
    opportunity_type="cross-sell",
    requires=["veeam_vbr", "m365"],
    absent=["vdc365"],
    justification="Cliente tem Veeam VBR e M365, mas não tem VDC365.",
)

opportunities = evaluate_rules(portfolio, [rule])

print(opportunities[0].type)        # "cross-sell"
print(opportunities[0].evidence)    # ["veeam_vbr", "m365"]
print(opportunities[0].status)      # OpportunityStatus.DETECTED
```

Nenhuma oportunidade é gerada sem evidência — se `requires` não bater
completamente, ou se algo em `absent` estiver presente, `evaluate_rules`
simplesmente não inclui essa regra no resultado.
