# 15 — Empacotamento, Instalação e Release

## Objetivo

Entregar o Lead.Tracker como módulo instalável do Tech.Forge.

## Artefato

O módulo deve ser empacotado no formato `.mod` conforme o contrato do Tech.Forge.

## Manifesto

Deve conter versão e compatibilidade da plataforma.

## Instalação

Validar:
1. descoberta;
2. validação;
3. instalação;
4. habilitação;
5. execução;
6. health check.

## Atualização

Ao atualizar:
- `.env` existente permanece;
- `.env-model` acompanha a versão;
- novas variáveis são adicionadas sem sobrescrever as existentes.

## Notificação

O header deve mostrar a versão atual.

Se existir uma versão nova:

```text
Atualização disponível
```

Inicialmente o usuário poderá baixar e instalar manualmente.

Atualização automática somente quando houver suporte confiável no Tech.Forge.

## GitHub

O repositório de desenvolvimento é:

`Lead.Tracker`

A distribuição deve respeitar o catálogo de módulos do ecossistema Tech.Forge.

## Checklist

- [ ] testes passando;
- [ ] secrets removidos;
- [ ] `.env-model` atualizado;
- [ ] manifesto atualizado;
- [ ] documentação atualizada;
- [ ] changelog atualizado;
- [ ] compatibilidade Tech.Forge validada;
- [ ] instalação testada;
- [ ] atualização testada;
- [ ] rollback considerado;
- [ ] `.mod` gerado;
- [ ] release publicada.

## Regra final

Nenhuma release deve depender de configuração específica da Triple S.

O contexto da empresa deve ser configurável pelo usuário.
