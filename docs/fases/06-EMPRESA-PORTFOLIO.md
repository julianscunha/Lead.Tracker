# 06 — Empresa e Portfólio

## Objetivo

Criar o contexto comercial da empresa usuária.

## Tela Empresa

Deve permitir:
- nome;
- website;
- descrição;
- sincronizar portfólio;
- visualizar portfólio;
- adicionar produto;
- remover produto;
- adicionar serviço;
- remover serviço;
- editar informações.

## Sincronização

```text
Website
 ↓
Coleta
 ↓
Extração
 ↓
IA
 ↓
Portfólio candidato
 ↓
Validação
 ↓
Usuário escolhe:
  Adicionar
  Sobrescrever
 ↓
Portfólio salvo
```

## Regra

Nunca alterar o portfólio existente sem confirmação quando houver dados armazenados.

### Adicionar

Mantém o conteúdo atual e acrescenta itens novos.

### Sobrescrever

Substitui o portfólio atual pelo resultado validado.

## Produtos e serviços

Produtos e serviços devem ser armazenados separadamente.

## IA

A IA pode interpretar o website, mas:
- não pode inventar produtos;
- deve indicar evidência;
- deve devolver estrutura validável;
- deve permitir edição humana.

## Mapa de correlação

O portfólio pode conter relações como:

```text
Veeam VBR
 ├── VDC365
 ├── Kasten
 └── DR

VMware VVF
 └── VCF
```

Essas relações podem ser manuais ou posteriormente mantidas por regras.
