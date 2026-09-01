# Lead.Tracker — Ordem Oficial de Desenvolvimento

Este documento define a ordem obrigatória de implementação do projeto.

## Regra principal

O desenvolvimento deve seguir estritamente a sequência:

`01 → 02 → 03 → ... → 15`

Nenhuma etapa posterior deve introduzir arquitetura que contradiga decisões anteriores.

Uma etapa somente poderá alterar uma decisão anterior quando houver justificativa técnica, testes e registro em `14-DECISOES.md`.

## Resultado esperado

Ao final, o Lead.Tracker será um módulo instalável do Tech.Forge, contendo:

- backend Python/FastAPI;
- frontend React/TypeScript compatível com o Module Host do Tech.Forge;
- SQLite para persistência local;
- providers desacoplados;
- integração opcional com Salesforce;
- descoberta e gerenciamento do portfólio da empresa;
- produtos e serviços;
- motor de oportunidades;
- IA contextual;
- filtros e rankings;
- dashboard executivo;
- exportação PDF;
- exportação tabular;
- geração de rascunho de e-mail;
- tratamento robusto de erros;
- testes;
- empacotamento `.mod`.

## Sequência oficial

1. Arquitetura e limites
2. Modelo de dados
3. Configuração e segredos
4. Esqueleto do módulo Tech.Forge
5. Camada de providers
6. Empresa e portfólio
7. Coleta e normalização de dados
8. Motor de oportunidades
9. Camada de IA
10. Interface operacional
11. Dashboard executivo
12. Exportações e rascunho de e-mail
13. Resiliência, erros e observabilidade
14. Testes, decisões e documentação técnica
15. Empacotamento, instalação e release

## Regra de implementação

Não começar pela IA, scraping ou Salesforce real.

Primeiro construir contratos, modelos e fluxo determinístico. Depois adicionar integrações e inteligência.
