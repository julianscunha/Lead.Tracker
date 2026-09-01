# 07 — Coleta e Normalização de Dados

## Objetivo

Transformar dados heterogêneos em registros comparáveis.

## Pipeline

```text
Provider
 ↓
Dados brutos
 ↓
Validação
 ↓
Normalização
 ↓
Deduplicação
 ↓
Empresa unificada
```

## Normalização

Considerar:
- razão social versus nome fantasia;
- domínios;
- telefones;
- identificadores empresariais quando disponíveis e permitidos;
- nomes de produtos;
- aliases de fabricantes.

## Deduplicação

Uma empresa encontrada no Salesforce e no website deve resultar em uma única Company.

## Proveniência

Manter a origem dos dados relevantes.

## Identificação de cliente

Uma empresa será marcada como cliente quando houver evidência confiável de relacionamento ativo.

Um registro antigo ou uma oportunidade perdida não deve ser considerado cliente ativo automaticamente.

## Dados externos

Podem enriquecer:
- tamanho;
- localização;
- segmento;
- presença;
- tecnologias observáveis;
- sinais de expansão.

A origem deve ser preservada.

## Regra

Nunca transformar uma inferência em fato sem marcá-la como inferência.
