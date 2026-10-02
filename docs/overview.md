---
title: "Lead.Tracker — Visão geral"
order: 1
tags: [lead-tracker, visao-geral, oportunidades, portfolio, fontes-de-dados]
---

# Lead.Tracker

Módulo de Opportunity Intelligence para o Tech.Forge. Transforma dados de
clientes, prospects, portfólio tecnológico, produtos e serviços em
oportunidades comerciais priorizadas — cross-sell, up-sell, modernização,
otimização de custos — sempre com motivo e evidência, nunca um palpite.

## O que o módulo faz

- **Consolida** empresas vindas de múltiplas fontes (Salesforce, Google Maps,
  importação por planilha) numa única `Company`, sem duplicação — a mesma conta
  nunca aparece duas vezes só porque veio de fontes diferentes.
- **Detecta oportunidades** por regras determinísticas de correlação de
  portfólio (presença/ausência de produto ou serviço) e por sinais de
  expansão (renovação próxima, adoção parcial, mudança de contato-chave) —
  toda oportunidade carrega fato, implicação de negócio, fonte e data.
- **Quantifica o tamanho do gap** — alcance (isolado/parcial/generalizado)
  × criticidade viram uma severidade clara, qualificada pelo vendedor.
- **Acompanha o funil** com status auditável (detectada → qualificada →
  revisada → contatada → oportunidade, ou descartada com motivo
  categorizado) e histórico completo de cada transição.
- **Cuida da carteira** — saúde de conta e sugestão de quando revisar cada
  cliente (cadência de QBR baseada em renovação + saúde da conta, nunca
  aleatória), alerta de oportunidade zumbi (parada há tempo demais no
  mesmo estágio) ou envelhecida (nunca saiu da triagem inicial).
- **Prospecta geograficamente** via Google Maps — a partir de um perfil de
  cliente ideal configurável (ou derivado automaticamente dos seus
  clientes satisfeitos), encontra empresas parecidas num raio, com
  pontuação em camadas e um limite diário anti-spam por representante.
- **Se adapta ao seu Salesforce** — descobre os campos personalizados da
  sua conta e deixa você associar cada um a um papel de negócio via
  dropdown (nunca API name na tela), avisando quando um mapeamento quebra
  (campo renomeado/removido do lado do Salesforce).
- **Ajuda a escrever o contato** — gera rascunho de e-mail persuasivo com
  guardas determinísticas contra alucinação (nunca urgência falsa, nunca
  "clientes como você" sem caso real citado nos dados) e sugere o próximo
  passo por oportunidade (canal, motivo, cadência) — sempre uma sugestão
  que você confirma copiando e marcando como enviado, nunca um disparo
  automático.
- **Completa porte e setor das empresas** — a API de dados de empresas que você
  configurar em Entrada de dados preenche setor e número de funcionários só onde
  estão vazios; se discordar de outra fonte, vira conflito para você resolver.
- **Monta o portfólio a partir do seu site** — a IA sugere fabricantes, produtos
  e serviços lendo o site da sua empresa (endereço informado em Configurações),
  cada sugestão com o trecho do site que a comprova; só entra no portfólio o que
  você marcar e adicionar. Sem IA configurada o cadastro continua manual.
- **Respeita quem não quer ser contatado** — lista de "não contatar" por
  empresa ou contato, por canal ou em todos; bloqueia a sugestão de toque e o
  rascunho de e-mail, e exige confirmação explícita para registrar um
  contato mesmo assim (fica marcado para auditoria).
- **Mantém o dado confiável entre fontes** — valor atualizado pela mesma
  fonte substitui o antigo e fica registrado; valores diferentes vindos de
  fontes diferentes viram um conflito para o usuário escolher, nunca
  sobrescrita silenciosa.
- **Registra o que mudou** — histórico de alterações por oportunidade, com
  antes e depois, quando e por quem; textos pessoais nunca são gravados.
- **Avisa quando algo esfria** — sinaliza oportunidades em qualificação
  inicial que ficaram sem contato por tempo além do esperado, pra você
  decidir (nunca muda status sozinho).
- **Complementa com IA** (opcional — OpenRouter, OpenAI, Gemini ou Claude)
  pra interpretar, correlacionar, enriquecer e redigir. A IA nunca decide
  sozinha que uma oportunidade existe, nunca inventa produto fora do
  portfólio configurado, nunca envia nada automaticamente.
- **Mostra o panorama** — dashboard executivo com KPIs, funil, distribuição
  por fabricante/serviço e cobertura de meta por representante, tudo
  derivado de dado real.
- **Exporta** PDF e Excel em toda tela de resultado.

## Como o módulo se organiza (telas)

O fluxo segue a ordem de trabalho: ver → trazer dados → lapidar e agir → calibrar.

- **Dashboard** — visão executiva: o que pede decisão hoje (cada número leva à
  lista de oportunidades já filtrada), valor do pipeline e funil; cobertura de
  meta por representante e demais indicadores ficam recolhidos; exportação
  executiva em PDF.
- **Entrada de dados** — porta de entrada única: atualizar dados das fontes,
  conectar Salesforce, Google Maps, o site da empresa e uma API de enriquecimento, importar planilha CSV e
  fazer a prospecção geográfica (assistente guiado: produto de referência →
  raio → revisão do critério sugerido → confirmar).
- **Oportunidades** — lapidar e agir: a lista viva de tudo que o motor
  encontrou, com status e saúde da conta; filtra por status, saúde, cliente/
  prospect, produto/serviço, fonte e score; mostra os conflitos de dados entre
  fontes quando existem; cada linha expande para mudar status, ver a próxima
  ação sugerida, marcar "não contatar", gerar rascunho de e-mail e business
  case, preencher a discovery, qualificar o gap e consultar o histórico de
  alterações. Exporta PDF e Excel.
- **Configurações** — calibragem de uso mais raro, em seções recolhíveis:
  portfólio (inclui sugestão pelo site), regras (com sugestão opcional por IA,
  que você aceita ou ignora uma a uma), mapeamento de campo
  personalizado do Salesforce, IA, limites e prazos, metas por representante.

O campo **Você é**, no topo, informa o representante uma única vez para todas as
abas.

## Arquitetura

- Backend: Python/FastAPI, persistência SQLite (SQLAlchemy async),
  migração de schema via Alembic.
- Frontend: React/TypeScript, compilado via Vite (ESM único, sem framework
  compartilhado com o Core).
- Domínio determinístico primeiro, IA depois: `core/opportunity_engine.py`
  gera oportunidades completas sem depender de nenhuma chamada de IA.
- Providers desacoplados de fonte de dado (`providers/`) — Salesforce é
  uma integração opcional entre várias, nunca um conceito de primeira
  classe no núcleo.

## Configuração

Ver tela de Configurações do módulo (ou `.env` durante desenvolvimento) para
`AI_PROVIDER`/`AI_API_KEY` (opcional), `SALESFORCE_*` e `GOOGLE_MAPS_*`
(integrações opcionais, desligadas por padrão).

## Documentação completa

Ver `README.md` e `CONTRIBUTING.md` neste repositório para arquitetura,
comandos de desenvolvimento e regras de domínio. Ver
`docs/criterios-de-qualificacao.md` para o que cada critério de
priorização de oportunidade significa e por que o número/threshold é
esse (recência de atividade, nível hierárquico do contato, severidade de
gap). Ver `docs/TROUBLESHOOTING.md` para problemas comuns de instalação/
configuração.

Para quem desenvolve (não é guia de uso do produto): o que já foi
construído está em `docs/implementacao/`, o que ainda falta em `docs/roadmap.md`
e as regras do produto em `docs/principios.md`.
