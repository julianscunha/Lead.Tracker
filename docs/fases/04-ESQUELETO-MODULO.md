# 04 — Esqueleto do Módulo Tech.Forge

## Objetivo

Criar primeiro um módulo vazio, porém instalável, executável e saudável.

## Contrato

Seguir o padrão de módulos do Tech.Forge:
- `manifest.yaml`;
- entrypoint do backend;
- entrypoint do frontend;
- lifecycle;
- health check;
- documentação.

## Estrutura inicial

```text
Lead.Tracker/
├── manifest.yaml
├── backend/
│   └── main.py
├── frontend/
│   └── index.js
├── core/
├── providers/
├── ai/
├── exports/
├── data/
├── docs/
└── tests/
```

## Manifesto

Deve declarar:
- id;
- nome;
- versão;
- versão mínima do Tech.Forge;
- versão máxima compatível;
- categoria;
- tipo de módulo;
- fornecedor;
- autor;
- descrição;
- ícone;
- ordem;
- entrypoint do backend;
- entrypoint do frontend.

## Critério de conclusão

O módulo deve:
1. instalar;
2. habilitar;
3. abrir;
4. responder ao health check;
5. desabilitar;
6. reinstalar;
7. desinstalar.

Somente depois avançar para a etapa seguinte.
