# Contribuindo com o Lead.Tracker

Obrigado pelo interesse em contribuir! Este documento resume o essencial pra
começar.

## Regras de domínio que todo PR precisa respeitar

Essas não são só estilo — são decisões arquiteturais já tomadas, quebrar
elas é motivo de mudança pedida na review:

- **Regras determinísticas vêm antes de IA.** O motor de oportunidades
  (`core/opportunity_engine.py`) funciona 100% sem IA configurada. IA é
  complementar — nunca decide sozinha, nunca inventa produto/serviço fora
  do portfólio, nunca envia e-mail automaticamente.
- **Nenhuma oportunidade sem evidência.** Toda `Opportunity` carrega
  `evidence`/`sources`/`confidence_score`.
- **`Company` é a entidade unificada** — nunca duplicar uma empresa por
  aparecer em fontes diferentes; normalização consolida (`core/normalization.py`).
- **Score ≠ potencial financeiro.** `opportunity_score`, `financial_potential`,
  `strategic_score` e `confidence_score` são campos distintos — nunca
  colapsar num número só, e nunca inventar valor pra campo sem dado real
  (`None` fica `None`).
- **Secrets nunca aparecem** em logs, prompts de IA, exports ou mensagens de
  erro (`core/errors.py`, `build_structured_prompt`).
- **Núcleo genérico.** Nada de fabricante/portfólio/regra comercial
  hardcoded — tudo configurável.

## Rodando localmente

```bash
# Backend
pip install -r backend/requirements.txt
python tests/test_models.py   # ... e os demais tests/test_*.py (scripts standalone)

# Frontend
cd frontend && npm install && npm run build && npm run test
```

Ver `README.md` § "Testar contra o Tech.Forge Core de verdade" pra validar
mudanças contra o Core real, não só os testes unitários.

## Fluxo de contribuição

1. Abra uma issue descrevendo o problema/proposta antes de um PR grande —
   evita retrabalho se a direção não fizer sentido.
2. Todo bug fix vem com um teste de regressão que falha sem a correção
   (Prove-It Pattern) — sem exceção.
3. Toda mudança arquiteturalmente relevante merece uma explicação clara na
   descrição do PR: contexto, alternativas consideradas, escolha e motivo.
4. Rode a suíte completa (backend + frontend) antes de abrir o PR — zero
   regressão é o mínimo aceitável.
5. Nunca use dado real de cliente em teste ou exemplo — só empresas fictícias.

## Onde as coisas vivem

| Área | Local |
|---|---|
| Modelos de domínio | `core/models.py` |
| Motor de oportunidades | `core/opportunity_engine.py` |
| Providers (fontes de dado) | `providers/` |
| Camada de IA | `ai/` |
| Exportações (PDF/Excel/e-mail) | `exports/` |
| Persistência | `core/db.py`, `core/db_models.py`, `core/repository.py` |
| Backend HTTP | `backend/` |
| Frontend (React/TS) | `frontend/src/` |
| Testes | `tests/` (backend), `frontend/src/*.test.ts` (frontend) |

## Módulos do Tech.Forge

Este repositório é o desenvolvimento do módulo Lead.Tracker. O catálogo
oficial de módulos do ecossistema Tech.Forge é
[`Tech.Forge.Modules`](https://github.com/julianscunha/Tech.Forge.Modules) —
é lá que módulos publicados ficam disponíveis pra instalação. Para entender
o contrato de módulo em si (manifest, lifecycle, SDK), veja o repositório
[`Tech.Forge`](https://github.com/julianscunha/Tech.Forge).

## Dúvidas

Abra uma issue. Problemas de segurança devem ser reportados de forma privada
(veja o perfil do mantenedor no GitHub), não em issue pública.
