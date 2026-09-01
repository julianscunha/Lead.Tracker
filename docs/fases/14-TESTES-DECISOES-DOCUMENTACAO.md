# 14 — Testes, Decisões e Documentação

## Objetivo

Garantir estabilidade antes do empacotamento.

## Testes unitários

Cobrir:
- modelos;
- normalização;
- deduplicação;
- filtros;
- scoring;
- correlação;
- merge do portfólio;
- configuração;
- tratamento de erros.

## Testes de integração

Cobrir:
- provider mock;
- Salesforce mock;
- IA mock;
- exportação;
- persistência.

## Testes de interface

Cobrir fluxos críticos:
- abrir módulo;
- configurar empresa;
- sincronizar portfólio;
- filtrar clientes;
- expandir empresa;
- gerar rascunho;
- exportar PDF.

## Fixtures

Não usar dados reais de clientes em testes públicos.

Usar empresas fictícias.

## Regressão

Toda correção de bug deve criar ou atualizar um teste.

## Documentação

Manter:
- README;
- arquitetura;
- configuração;
- providers;
- IA;
- troubleshooting;
- notas de versão.

## Decisões

Registrar decisões arquiteturais relevantes em:

`DECISOES.md`

Formato:

```text
Data
Decisão
Contexto
Alternativas
Escolha
Motivo
Impacto
```

## Critérios

Não avançar para release com:
- testes críticos quebrados;
- secrets no repositório;
- integração sem timeout;
- erros técnicos expostos ao usuário.
