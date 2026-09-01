# 08 — Motor de Oportunidades

## Objetivo

Transformar contexto empresarial e tecnológico em oportunidades priorizadas.

## Princípio

O motor deve responder:

> Onde existe oportunidade de valor para esta empresa?

Não apenas:

> Que produto vender?

## Entradas

- portfólio;
- produtos atuais;
- serviços atuais;
- dados do CRM;
- dados externos;
- sinais de crescimento;
- contexto técnico;
- histórico;
- regras de correlação.

## Tipos

### Oportunidade de produto

Produto adicional, upgrade ou expansão.

### Oportunidade de serviço

Assessment, migração, sustentação, FinOps, DR, serviços gerenciados etc.

### Oportunidade de otimização

Redução de custos, consolidação, modernização ou mudança arquitetural.

## Métricas

Não usar um único score.

Mínimo:
- `opportunity_score`: aderência;
- `financial_potential`: potencial financeiro;
- `strategic_score`: valor estratégico;
- `confidence_score`: confiança dos dados.

## Regras

Regras determinísticas vêm antes da IA.

Exemplo:

```text
Veeam VBR presente
+
Microsoft 365 presente
+
VDC365 ausente
=
Oportunidade VDC365
```

## Evidências

Toda oportunidade deve ter:
- motivo;
- evidências;
- fontes;
- nível de confiança.

## Regra

Não gerar oportunidade sem evidência suficiente.

## Status

- detected
- qualified
- reviewed
- contacted
- opportunity
- dismissed
