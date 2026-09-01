# 01 — Arquitetura

## Objetivo

Definir a arquitetura do Lead.Tracker como módulo de negócio do Tech.Forge.

## Relação com o Tech.Forge

O Lead.Tracker não será uma aplicação independente no ambiente final. Será um módulo instalável.

O repositório `Lead.Tracker` é o repositório de desenvolvimento do módulo. O módulo deve respeitar o contrato do Tech.Forge e ser empacotável para instalação.

## Arquitetura

```text
Tech.Forge Core
       │
       └── Módulo Lead.Tracker
             │
             ├── Frontend React/TypeScript
             ├── Backend FastAPI/Python
             ├── Modelos de domínio
             ├── Camada de Providers
             │     ├── Salesforce
             │     ├── Website
             │     ├── Google Maps
             │     ├── CSV
             │     └── futuros providers
             ├── Motor de Portfólio
             ├── Motor de Correlação
             ├── Motor de Oportunidades
             ├── Camada de IA
             └── Camada de Exportação
```

## Regra de dependência

```text
Interface
 ↓
Serviços da aplicação
 ↓
Domínio / Motor de oportunidades
 ↓
Interfaces de Provider
 ↓
Sistemas externos
```

A interface não pode acessar Salesforce, Google Maps ou IA diretamente.

## Tecnologias

- Backend: Python + FastAPI
- Frontend: React + TypeScript
- Persistência: SQLite
- Configuração: `.env`
- Modelo de configuração: `.env-model`
- IA: abstração de provider
- PDF: camada isolada de exportação
- Empacotamento: `.mod` conforme o Tech.Forge

## Princípios

- local-first;
- baixo custo;
- modular;
- independente de fornecedor;
- IA assistiva, não autônoma;
- configuração simples;
- segurança por padrão;
- UX para usuários não técnicos;
- nenhuma integração externa obrigatória.
