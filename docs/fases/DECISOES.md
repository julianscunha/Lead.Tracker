# Lead.Tracker — Decisões Arquiteturais

## 001 — Módulo Tech.Forge

Lead.Tracker será um módulo do Tech.Forge.

## 002 — Um único módulo de negócio

Não criar inicialmente um módulo Salesforce separado.

Salesforce é um provider/integration do Lead.Tracker.

Se no futuro a integração Salesforce se tornar infraestrutura compartilhada por múltiplos módulos, poderá ser extraída.

## 003 — Abstração de providers

Fontes externas não devem aparecer como conceitos centrais do domínio.

O domínio trabalha com dados normalizados.

## 004 — Cliente é atributo

A interface utiliza `is_customer`/status de cliente.

Não existe uma tela específica chamada Salesforce.

## 005 — Fontes são metadados

Cada empresa pode ter múltiplas fontes.

Exemplo:

```json
"sources": ["salesforce", "website"]
```

## 006 — Produtos e serviços são diferentes

Produto e serviço possuem modelos próprios e podem gerar oportunidades independentes.

## 007 — Score não é valor financeiro

Score mede aderência.

Potencial financeiro mede retorno potencial.

Eles podem gerar rankings diferentes.

## 008 — IA complementar

IA não substitui regras determinísticas.

## 009 — Portfólio é autoridade comercial

A IA deve usar o portfólio configurado pela empresa como base para recomendações.

## 010 — Sincronização manual

Não existe scheduler obrigatório para o portfólio.

O usuário atualiza quando desejar.

## 011 — Atualização do portfólio

Ao encontrar dados existentes, o usuário escolhe:
- adicionar;
- sobrescrever.

## 012 — UI operacional em tabela

A tela de oportunidades prioriza tabela, filtros, ordenação e expansão.

## 013 — Dashboard separado da operação

O dashboard fornece visão executiva; a tabela fornece operação comercial.

## 014 — Local-first

O módulo deve funcionar localmente e minimizar custos de infraestrutura.

## 015 — Frontend Tech.Forge

O frontend final será React/TypeScript, compatível com o Module Host do Tech.Forge.

## 016 — Segurança

Secrets não entram no repositório, logs, prompts ou exports.

## 017 — Usuário leigo

Mensagens devem ser amigáveis e acionáveis.

## 018 — Desenvolvimento sequencial

As etapas numeradas são a ordem oficial de implementação.

## 019 — Repositório de desenvolvimento

O código será mantido no repositório `Lead.Tracker` e posteriormente empacotado como módulo do Tech.Forge.

## 020 — Open Source

O núcleo do projeto deve permanecer genérico e não depender de informações específicas de uma empresa. Portfólio, serviços, produtos, integrações e regras comerciais devem ser configuráveis.
