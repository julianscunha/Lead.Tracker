# Lead.Tracker

Módulo de Opportunity Intelligence para o Tech.Forge. Transforma dados de
clientes, prospects, portfólio tecnológico, produtos e serviços em
oportunidades comerciais priorizadas — cross-sell, up-sell, modernização,
otimização de custos — sempre com motivo e evidência, nunca um palpite.

## O que o módulo faz

- **Consolida** empresas vindas de múltiplas fontes (Salesforce, website,
  importação manual) numa única `Company`, sem duplicação — a mesma conta
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

- **Dashboard** — visão executiva agregada: KPIs, gráficos, oportunidades
  paradas, cobertura de meta por representante, exportação executiva em
  PDF.
- **Oportunidades** — a lista viva de tudo que o motor encontrou: filtra
  por cliente/prospect, produto/serviço, score; expande qualquer linha
  pra ver evidências, mudar status, qualificar severidade, gerar rascunho
  de e-mail e ver a próxima ação sugerida.
- **Prospecção** — assistente guiado (produto de referência → raio →
  revisão do critério sugerido → confirmar) pra descoberta geográfica via
  Google Maps.
- **Configurações** — fontes de dado, portfólio (fabricantes/produtos/
  serviços, construído automaticamente a partir do seu website e revisável
  antes de valer), mapeamento de campo personalizado do Salesforce, IA,
  metas por representante.

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

Histórico de decisões técnicas e planejamento de evolução (uso interno de
desenvolvimento, não é guia de uso do produto) vive em `docs/roadmap.md` e
`docs/specs/`.
