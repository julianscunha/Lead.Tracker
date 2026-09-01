# 02 — Modelo de Dados

## Objetivo

Definir os modelos internos antes das integrações.

## Entidades principais

### Company

Representa uma empresa identificada.

Campos mínimos:
- `id`
- `name`
- `legal_name`
- `website`
- `is_customer`
- `customer_status`
- `sources`
- `created_at`
- `updated_at`

### Source

Representa a origem de uma informação.

Exemplos:
- `salesforce`
- `website`
- `google_maps`
- `csv`
- `manual`
- `ai`

### Vendor

Representa fabricante ou tecnologia.

Exemplos iniciais da empresa de referência:
- Veeam
- VMware
- AWS
- Red Hat

Esses fabricantes não devem ser fixados no core.

### Product

Produto pertencente a um fabricante.

Deve suportar:
- nome;
- aliases;
- descrição;
- status;
- relações;
- serviços relacionados.

### Service

Serviço oferecido pela empresa usuária.

Produto e serviço são entidades independentes.

### Opportunity

Representa uma oportunidade identificada.

Deve suportar:
- empresa;
- tipo;
- fabricante;
- produto;
- serviço;
- score de oportunidade;
- potencial financeiro;
- score estratégico;
- score de confiança;
- evidências;
- justificativa;
- fontes;
- status.

### Portfolio

Representa o contexto comercial da empresa usuária.

Contém:
- empresa;
- fabricantes;
- produtos;
- serviços;
- relações;
- observações;
- última atualização.

## Cliente versus prospect

`is_customer` é atributo da Company, e não da integração Salesforce.

Salesforce é somente uma das possíveis fontes para determinar esse atributo.

## Fontes

Informações relevantes devem manter rastreabilidade.

Exemplo:

```json
{
  "sources": [
    {
      "type": "salesforce",
      "confidence": 1.0
    },
    {
      "type": "website",
      "confidence": 0.8
    }
  ]
}
```

## Regra

Não duplicar uma empresa porque ela apareceu em fontes diferentes. A camada de normalização deve consolidar os registros.
