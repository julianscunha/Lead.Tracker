# Changelog

## [Unreleased]

### Adicionado

- **Meta e cobertura por representante/período** (Fase D, módulo 7):
  cadastro manual de meta comercial por rep + período (mensal/trimestral,
  `POST`/`GET /rep-targets`); `GET /dashboard-metrics` ganha
  `rep_coverage` (pipeline atual ÷ meta) lido do snapshot diário. Rep sem
  meta cadastrada nunca mostra 0% nem divide por zero — `coverage_ratio`
  fica `null`, distinto de uma meta explicitamente cadastrada como 0.
  Recadastrar meta pro mesmo rep+período é upsert (id determinístico via
  uuid5), nunca duplica. `period_key` validado contra o formato exato do
  período (achado da revisão de código: texto livre permitia typo que
  criava meta "órfã" silenciosa); UI usa `<input type="month">`/`<select>`
  de trimestre em vez de texto livre. Ver
  `docs/specs/fase-d-dashboard-acionavel.md`.

- **Motivo categorizado de descarte** (Fase D, módulo 6): mudar uma
  oportunidade pra "Descartada" agora exige um `dismissal_reason` de um
  enum fechado (sem evidência / sem fit / cliente não qualificado / falso
  positivo de regra / outro — 4 categorias do roadmap + escape hatch
  sugerido em consulta ao Pipeline Analyst). Motivo persiste no histórico
  de transições mesmo depois de reaberta e descartada de novo com outro
  motivo (achado da revisão de código: guardar só no registro "atual"
  perdia motivos anteriores a cada ciclo reabrir→descartar). UI mostra o
  dropdown de motivo só ao selecionar "Descartada" e exibe o motivo já
  salvo. Ver `docs/specs/fase-d-dashboard-acionavel.md`.

- **Alerta de SLA de triagem / aging** (Fase D, módulo 5): oportunidade
  parada em "Detectada" além de um prazo configurável (`AGING_SLA_DAYS`,
  padrão 7 dias, via `GET`/`PUT /settings/config/aging-sla-days`) fica
  marcada `is_aging` em `GET /opportunities`; `GET /dashboard-metrics`
  ganha `aging_count`/`aging_sla_days` lidos do snapshot diário. Conceito
  deliberadamente distinto de "zumbi" (módulo 2+3): aging é só sobre
  triagem inicial nunca acontecer, zumbi é sobre qualquer estágio parado
  há muito tempo — nunca compartilham constante.

- **Agregador do dashboard via snapshot** (Fase D, terceiro módulo):
  `GET /dashboard-metrics` ganha potencial financeiro ponderado (bruto ao
  lado de duas somas ponderadas — avaliado por confidence_score real, e
  estimado incluindo as sem avaliação, nunca misturadas sem rótulo),
  cortes por rep/segmento/fonte (sempre segmentados, nunca um total
  misturado), contagem de oportunidade zumbi e um "alcance do funil"
  cumulativo. Consultei o Pipeline Analyst sobre a metodologia do alcance
  de funil: como o snapshot só guarda o estágio atual (não o histórico
  completo de transições), não é uma taxa de conversão de coorte de
  verdade — nomeado deliberadamente "alcance"/`reach`, nunca
  "conversão"/`conversion`, em qualquer variável, docstring ou campo de
  API. Zumbi nunca entra no potencial ponderado nem nos cortes (blindagem
  do roadmap), mas é contado e exposto à parte. Ver
  `docs/specs/fase-d-dashboard-acionavel.md`.

- **Snapshot diário de oportunidades e detecção de zumbi** (Fase D,
  segundo módulo): nova tabela `opportunity_snapshots`, recalculada por
  inteiro no fim de todo `POST /sync` — o dashboard (próximos módulos) vai
  ler daqui, nunca das tabelas transacionais em tempo real. Oportunidade
  parada há mais de 30 dias no mesmo estágio (sem `dismissed`, que nunca é
  zumbi) é marcada `is_zombie`. Corrigido um achado crítico da revisão de
  código: a primeira versão usava `synced_at` como proxy de "última
  atividade", mas esse campo é reescrito a cada `/sync` que ainda detecta
  a mesma oportunidade — isso neutralizaria o zumbi pra exatamente as
  oportunidades nunca revisadas por ninguém. Novo campo
  `Opportunity.first_detected_at`, gravado só na criação, nunca mais
  tocado, resolve isso. Ver `docs/specs/fase-d-dashboard-acionavel.md`.

- **Transição manual de status da oportunidade** (Fase D, primeiro módulo):
  dropdown de status na linha expansível, sem máquina de estados no
  domínio — mas pular 2+ estágios de uma vez ou reabrir uma oportunidade
  descartada exige uma justificativa (`PATCH /opportunities/{id}/status`,
  422 amigável sem nota). Corrigido um bug pré-existente descoberto
  durante o planejamento: o motor de regras resetava o status pra
  `detected` a cada `/sync`, porque a coluna entrava no upsert de
  atualização — como nunca existia forma de mudar status manualmente, o
  bug nunca tinha disparado. `OpportunityStatusChange` (histórico de
  transição, já existia no modelo desde a Fase B) passa a ser gravado de
  verdade, na mesma transação da mudança de status. Ver
  `docs/specs/fase-d-dashboard-acionavel.md` para o detalhamento.

- **Cadência de revisão de conta (QBR)**: última capacidade planejada da
  Fase C. A linha expansível de cada oportunidade ganha a saúde da conta
  (Saudável/Atenção/Crítica/Dados insuficientes, sempre derivada — pior
  entre recência de atividade e confiança média das oportunidades abertas,
  nunca uma média que esconderia um problema) e uma sugestão de prazo pra
  próxima revisão, combinando saúde × prazo até a renovação do contrato ×
  nº de sinais de risco/expansão em aberto — tabela fixa, nunca calendário
  igual pra toda conta. Novo campo manual `Company.renewal_date` e rota
  `PATCH /companies/{id}/renewal-date`. Revisão de código encontrou a mesma
  classe de risco já corrigida na severidade: `save_company` (caminho do
  sync) também virou upsert atômico que nunca sobrescreve `renewal_date`
  preenchido manualmente. Ver `docs/criterios-de-qualificacao.md` para o
  detalhamento da tabela. Fecha todos os itens planejados da Fase C.

- **Quantificação de gap por severidade**: tela de oportunidade ganha
  dois dropdowns (Alcance, Criticidade) e uma observação opcional,
  preenchidos manualmente pelo vendedor — sem fonte automática, sem
  número em R$ calculado pelo sistema. Uma banda de severidade
  (Baixo/Médio/Alto/Crítico) é derivada por tabela fixa dos dois campos,
  sempre recalculada na leitura (nunca fica dessincronizada). Nova rota
  `PATCH /opportunities/{id}`, validando o valor recebido (422 pra
  qualquer coisa fora das 3 opções de cada dropdown, nunca degrada
  silenciosamente pra "não avaliado"). `POST /sync` (motor de regras)
  nunca apaga esses campos manuais — a escrita usa um upsert atômico que
  não toca nessas 3 colunas, fechando também uma janela de concorrência
  entre uma sincronização e uma edição manual acontecendo ao mesmo
  tempo. Ver `docs/criterios-de-qualificacao.md` para o detalhamento de
  como a banda é calculada.

- **Sinais granulares de qualificação** (Fase C do roadmap, quarta fatia
  — parte 1, campos automáticos): `Company.last_activity_at`, mapeado do
  `LastActivityDate` do Salesforce, alimenta um multiplicador de
  `confidence_score` na geração de oportunidade — 3 níveis (quente até
  120 dias ×1.0, morno até 270 dias ×0.85, muito frio depois disso ou sem
  registro ×0.5; revisado com o agente especialista Pipeline Analyst após
  o corte binário original de 90 dias/×0.7 se mostrar curto demais pra
  ciclo de venda B2B de infraestrutura — ver
  `docs/criterios-de-qualificacao.md` pro raciocínio completo).
  `Contact.seniority_tier` é inferido
  automaticamente por palavra-chave do cargo (`decisor`/
  `influenciador_tecnico`/`operacional`), sem correspondência fica vazio
  — nunca inventa classificação. Edição manual do nível hierárquico fica
  pra uma fatia futura (ainda não existe rota de edição de contato no
  projeto). Corrigido de quebra um bug real descoberto nesta fatia:
  `merge_pair` (reconciliação entre fontes) congelava todo campo já
  preenchido no primeiro sync — `last_activity_at` nunca se atualizaria
  depois disso; agora prefere sempre o valor mais recente do fetch.

- **Formato de evidência rico** (Fase C do roadmap, terceira fatia):
  toda oportunidade gerada pelo motor agora traz `evidence_summary` —
  frase montada automaticamente no formato "fato → oportunidade/risco →
  fonte, sincronizado em" (princípio 2 do roadmap), nunca mais só uma
  lista de ids crus. Regra ganha `discovery_prompt` opcional (a pergunta
  que o vendedor deveria fazer pra confirmar a causa raiz, nunca a
  resposta), propagada pra `Opportunity.discovery_prompt`. Campos
  existentes (`evidence`, `justification`, `sources`) continuam intactos
  — só ganham uma camada de leitura pronta em cima.

- **Sinais de expansão no motor de regras** (Fase C do roadmap, segunda
  fatia): `CompanySignal` aberto (`status="open"`) agora entra no mesmo
  mecanismo de presença/ausência já existente — `signal_type` conta como
  item presente ao lado de `product_id`/`service_id` do portfólio, sem
  criar um 4º tipo de regra. Sinal resolvido/descartado nunca dispara
  regra. `POST /sync` carrega os sinais de cada empresa sincronizada e os
  passa pro motor. Ainda não existe fonte que gere `CompanySignal`
  automaticamente (fica pra quando Salesforce/Manual ligarem isso a dado
  real de CRM) — esta fatia só garante que, uma vez que o sinal exista, o
  motor reage a ele.

- **Motor de regras ampliado** (Fase C do roadmap, primeira fatia):
  `CorrelationRule` vira modelo persistido (`GET`/`POST /rules`) com 3
  mecanismos — presença/ausência simples, categoria
  (`requires_category`/`absent_category`, via `Product`/`Service.category`
  da Fase B) e relação tipada (`relation_type`, via
  `Product.related_services` da Fase B): `prerequisite` sinaliza
  `Opportunity.risk_flag` (nunca inventa oportunidade de venda fake),
  `substitute` gera oportunidade de consolidação. `POST /sync` agora roda
  o motor contra o portfólio já conhecido de cada empresa sincronizada —
  empresa sem portfólio cadastrado não gera nada (honesto, não é bug).
  Editor de regras na tela de Configurações: sempre por dropdown
  alimentado pelo catálogo real (`GET /products`/`GET /services`), nunca
  campo de texto livre pro item/categoria que dispara a regra.

- **Ligação real** (Fase B.1 do roadmap): o módulo para de rodar sobre dado
  fictício. Botão "Atualizar dados" (Configurações) aciona
  `POST /sync`, que busca empresas/contatos de cada fonte habilitada,
  normaliza (dedup dentro da própria fonte) e reconcilia contra empresa já
  persistida de OUTRA fonte antes de salvar (`core/normalization.dedup_key`/
  `merge_pair`, agora públicas) — nunca duplica empresa por aparecer em
  fontes diferentes, mesmo com IDs nativos distintos por provider; busca de
  contato continua usando o ID nativo do provider mesmo quando a empresa é
  reconciliada pra um ID já existente. `GET /companies`, `GET
  /opportunities` e `GET /dashboard-metrics` leem do
  banco — frontend (`Dashboard`, `Oportunidades`) trocou
  `sampleData.ts`/`sampleMetrics.ts` por chamada real, com estado de
  carregamento e vazio em linguagem de negócio. Falha de uma fonte nunca
  aborta as outras nem propaga exceção crua — sempre erro amigável por
  fonte. **Geração de oportunidade por regra continua pendente da Fase C**
  (não existe ainda persistência de regra de correlação) — `GET
  /opportunities` é honesto: devolve vazio até lá, nunca dado inventado.

- Fundação de modelo de dados (Fase B do roadmap): `Company` ganha
  `rep_id`/`segment`/`region`/`trigger_event`/`attempted_solutions`/
  `strategic_context`; `Contact` ganha `impacted_area`; `Product`/`Service`
  ganham `category`; `Product.related_service_ids` (lista de strings) vira
  `Product.related_services` (lista de `ProductRelation`, com
  `relation_type` — `prerequisite`/`complementary`/`substitute` por
  convenção, não `Enum` fechado). Dois modelos/tabelas novos:
  `CompanySignal` (sinal de expansão/risco, `signal_type` string aberta) e
  `OpportunityStatusChange` (histórico de transição de status). Todos os
  campos novos ficam `None`/vazios até uma fonte real preenchê-los — nada
  inventado. Sem tela, sem rota nova — só schema/modelo e persistência.
- `SalesforceProvider`: primeira fonte de dados real além do `ManualProvider`.
  Autentica via OAuth 2.0 Client Credentials Flow, consulta `Account`/`Contact`
  via SOQL (REST API), pagina resultados automaticamente. Erros técnicos nunca
  vazam brutos — categorizados em `CONFIGURATION`/`AUTHENTICATION`/`TIMEOUT`/
  `CONNECTIVITY`/`INTEGRATION`; retry só em erro transitório (429/5xx), nunca
  em credencial inválida. Sessão expirada em pleno uso (401 no meio de uma
  consulta) reautentica uma única vez antes de desistir — só vira erro de
  credencial se a sessão nova também falhar. `company_id` validado contra o
  formato exato de ID do Salesforce (15 ou 18 caracteres) antes de entrar em
  qualquer SOQL (evita injeção).
- Tela de **Configurações de Fontes** (Fase 0 do roadmap): liga/desliga cada
  fonte (Manual sempre disponível; Salesforce configurável; Website/Google
  Maps aparecem como "em breve" até os providers existirem), com formulário
  de credencial em português e teste de conexão automático ao ligar —
  indicador 🟢/🔴/⚪ ao lado do toggle. Nenhum segredo volta em claro em
  nenhuma resposta de API. Nova rota `PUT /settings/{id}` grava valor no
  `.env` sem apagar chave não mencionada (`set_env_values` em
  `core/config.py`, complementa `sync_env`) — rejeita valor com quebra de
  linha (evita injeção de chave nova no arquivo) e corrige chave duplicada
  mantendo só a ocorrência com o valor novo.

### Corrigido

- `SalesforceProvider._authenticate`: resposta 200 com corpo inesperado do
  Salesforce (sem `access_token`/`instance_url`) não vazava mais como
  `KeyError`/`JSONDecodeError` cru — vira `ProviderError` categorizado.

### Alterado

- Renomeado `env-model` de volta para `.env-model` — o Tech.Forge Core
  v1.1.0 passou a permitir esse dotfile explicitamente no empacotamento
  (`ALLOWED_DOTFILES` no `PackageBuilder`), então o workaround de nome sem
  ponto não é mais necessário. `platform_min_version` subiu para `1.1.0`
  no manifest por causa dessa dependência.

## [0.1.0] - 2026-09-01

Primeira release.

### Adicionado

- Modelos de domínio (Pydantic): `Company`, `Vendor`, `Product`, `Service`,
  `Contact`, `Opportunity`, `Portfolio`.
- Sincronização `.env`/`env-model`: adiciona chaves ausentes, nunca
  sobrescreve ou remove valores existentes.
- Contrato `DataProvider` + `ManualProvider` de referência (in-memory, sem
  chamada externa).
- CRUD de produto/serviço no portfólio + merge Adicionar/Sobrescrever.
- Deduplicação de empresas por domínio/nome, preservando proveniência das
  fontes.
- Motor de oportunidades determinístico: regras de correlação
  (`CorrelationRule`/`evaluate_rules`) — `financial_potential`/
  `strategic_score` nunca inventados sem dado real.
- Camada de IA complementar e opcional: contrato `AIProvider` + OpenRouter
  (padrão), OpenAI, Gemini, Claude. Prompt sempre exige JSON estruturado com
  evidência e confiança, nunca inventa produto/serviço fora do portfólio.
- Frontend React/TypeScript (Vite, build próprio): tela de Oportunidades
  (filtros, ordenação, linha expansível) e Dashboard Executivo (KPIs,
  distribuição por fabricante, potencial por fabricante e por serviço,
  cliente×prospect, funil — tudo derivado de dado real, paleta categórica
  validada para acessibilidade).
- Exportação em PDF (tabela de oportunidades + executivo) e Excel.
- Rascunho de e-mail via IA — nunca envia automaticamente, nunca inventa
  campo ausente.
- Taxonomia de erro unificada (`DomainError`/`ErrorCategory`) com mapeamento
  categoria→status HTTP consistente em toda a API.
- Persistência real: SQLite via SQLAlchemy async.
- Módulo empacotado (`.mod`) e validado ponta a ponta contra o Tech.Forge
  Core real: instalação, ativação, `health_check()`, banco de dados.

### Corrigido

- Fonte core do fpdf2 quebrava a exportação em PDF com caracteres fora de
  latin-1 (travessão, aspas curvas, emoji).
- Tabelas do banco nunca eram criadas em produção (classes ORM não
  registradas antes do `create_all()`).
- SQLite descartava o timezone dos campos de data/hora na leitura.
- O builder de pacotes do Tech.Forge exclui todo arquivo começando com
  ponto — o arquivo de configuração modelo foi renomeado de `.env-model`
  para `env-model` para sobreviver ao empacotamento.

### Plano de rollback

Sem servidor de produção compartilhado (módulo local-first) — rollback é
reinstalar a versão anterior do `.mod`:

1. Manter o `.mod` da versão anterior guardado (não é sobrescrito pelo build).
2. Desinstalar a versão nova via o Package Manager do Tech.Forge.
3. Instalar o `.mod` anterior.
4. `.env` do usuário nunca é tocado por instalar/desinstalar — `sync_env()`
   só adiciona chave nova, nunca remove — dado de configuração sobrevive ao
   rollback.
5. O banco (`data/lead_tracker.db`) não é apagado ao desativar o módulo, só
   ao desinstalar explicitamente — reinstalar a versão anterior preserva os
   dados já persistidos, contanto que o schema seja compatível (sem
   migração formal ainda).
