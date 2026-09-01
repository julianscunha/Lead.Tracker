# 09 — Camada de IA

## Objetivo

Usar IA para complementar dados determinísticos.

## Contexto enviado à IA

```text
Contexto da empresa
+
Portfólio
+
Produtos
+
Serviços
+
Regras de correlação
+
Dados dos providers
```

## A IA pode

- interpretar texto livre;
- extrair sinais;
- correlacionar contexto;
- identificar gaps;
- enriquecer justificativas;
- gerar resumo executivo;
- gerar rascunho de e-mail.

## A IA não pode

- inventar produtos;
- inventar serviços;
- ignorar o portfólio;
- alterar dados de origem;
- decidir sozinha que uma oportunidade existe;
- enviar e-mail automaticamente.

## Portfólio como autoridade

O portfólio local é a autoridade comercial.

O website da empresa é usado para construir ou atualizar esse contexto.

## Saída estruturada

Prompts devem exigir:
- estrutura previsível;
- evidências;
- confiança;
- ausência de invenção;
- recomendações somente dentro do portfólio fornecido.

## Abstração de provider

```text
AIProvider
├── OpenAI
├── Gemini
└── futuros providers
```

## Custo

A IA somente deve ser chamada quando agregar valor.

Não usar IA para:
- filtros;
- ordenação;
- cálculos;
- validações simples;
- dados já estruturados.

## Cache

Resultados que não precisam ser recalculados devem ser persistidos localmente.
