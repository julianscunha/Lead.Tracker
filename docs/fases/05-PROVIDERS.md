# 05 — Camada de Providers

## Objetivo

Evitar acoplamento do domínio a Salesforce ou qualquer fonte específica.

## Interface conceitual

```python
class DataProvider:
    id: str

    async def test_connection(self): ...
    async def fetch_companies(self): ...
    async def fetch_contacts(self): ...
    async def fetch_context(self): ...
```

Os contratos definitivos devem ser determinados pelos modelos reais.

## Providers iniciais

### SalesforceProvider

Fonte opcional de:
- empresas;
- contatos;
- oportunidades;
- produtos;
- itens de oportunidade;
- outros objetos necessários.

### WebsiteProvider

Fonte para:
- website;
- páginas;
- produtos;
- serviços;
- especialidades.

### ManualProvider

Permite dados adicionados pelo usuário.

## Providers futuros

- Google Maps;
- HubSpot;
- Pipedrive;
- CSV;
- LinkedIn;
- outros.

## Regra

Provider coleta e normaliza dados. Não decide oportunidades.

Provider não deve:
- calcular score;
- gerar e-mail;
- executar prompts;
- controlar interface.

## Salesforce

Preferir OAuth 2.0.

A integração deve suportar:
- teste de conexão;
- descoberta de estrutura quando necessária;
- mapeamento de campos;
- sincronização;
- token expirado;
- paginação;
- limites de API;
- retry controlado.

## Resultado

Todos os providers entregam dados à camada de normalização em um modelo comum.
