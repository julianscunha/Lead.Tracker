# 10 — Interface Operacional

## Objetivo

Criar uma interface simples e eficiente para usuários leigos.

## Navegação

```text
Dashboard
Oportunidades
Empresa
Integrações
Configurações
Logs
```

Não criar menu específico para Salesforce.

## Header

Deve mostrar:
- nome;
- versão;
- estado;
- atualização disponível.

## Oportunidades

A tela principal deve ter aparência semelhante a uma planilha.

Colunas sugeridas:

```text
Empresa
Cliente
Score
Potencial $
Produto
Serviço
Prioridade
Fontes
```

## Filtros

Mínimo:
- todos;
- clientes atuais;
- prospects;
- fabricante;
- produto;
- serviço;
- score;
- potencial financeiro;
- fonte.

## Ordenação

Mínimo:
- score;
- potencial financeiro;
- prioridade;
- confiança.

## Linha expansível

Ao clicar, mostrar:

- empresa;
- status de cliente;
- fontes;
- produtos atuais;
- produtos recomendados;
- serviços recomendados;
- potencial financeiro;
- scores;
- evidências;
- insights da IA.

Ações:
- copiar;
- gerar rascunho.

## Fontes

Ícones discretos podem indicar website, CRM, Google Maps e outras fontes.

O detalhe deve mostrar a origem completa.

## Cliente

Mostrar claramente:
- Cliente;
- Prospect.

Nunca depender somente de cor.

## UX

O usuário deve:
- entender o que aconteceu;
- saber como corrigir;
- nunca ver stack trace;
- nunca precisar editar arquivos manualmente.
