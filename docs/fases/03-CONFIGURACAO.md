# 03 — Configuração e Segredos

## Objetivo

Manter a configuração simples para o usuário e segura para credenciais.

## Arquivos

### `.env`

Contém os valores reais da instalação.

Nunca deve ser versionado.

### `.env-model`

Modelo de configuração distribuído com o módulo.

Pode evoluir entre versões.

## Regra de atualização

Ao iniciar ou instalar uma nova versão:

1. comparar `.env` com `.env-model`;
2. identificar variáveis novas;
3. adicionar somente variáveis ausentes;
4. nunca sobrescrever valores existentes;
5. nunca remover automaticamente variáveis antigas.

## Configurações esperadas

Exemplo:

```env
APP_ENV=local
LOG_LEVEL=INFO

AI_PROVIDER=
AI_API_KEY=

COMPANY_WEBSITE=

SALESFORCE_ENABLED=false
SALESFORCE_CLIENT_ID=
SALESFORCE_CLIENT_SECRET=
SALESFORCE_LOGIN_URL=

GOOGLE_MAPS_ENABLED=false
GOOGLE_MAPS_API_KEY=
```

Os nomes definitivos serão estabelecidos durante a implementação.

## Interface

O usuário não deve precisar editar `.env` manualmente.

A tela de configurações deve:
- apresentar campos amigáveis;
- salvar configurações;
- mascarar segredos;
- testar integrações;
- informar configurações obrigatórias ausentes.

## Segurança

Credenciais nunca devem aparecer:
- em tabelas;
- em logs;
- em mensagens de erro;
- em PDFs;
- em prompts de IA.
