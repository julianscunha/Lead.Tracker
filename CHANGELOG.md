# Changelog

## [Unreleased]

### Adicionado

- **Motor de cadência sugerida** (Fase G, módulo 6
  `suggested-cadence-engine`): função pura que sugere o próximo toque
  (canal + categoria de motivo) — cliente ativo (3 toques: uso atual
  → expansão → prova social, intervalos de 7 dias) e prospecção fria
  (2 toques: abertura → reforço, intervalo de 4 dias, para depois),
  com cap único de 25 toques/dia por representante somando as duas
  cadências. Nunca dispara nada — sempre depende do rep marcar como
  enviado. Decisões de cadência em consulta ao agente Outbound
  Strategist. Ver `docs/specs/fase-g-outreach-assistido.md`.

- **Histórico de toques de outreach** (Fase G, módulo 5
  `outreach-touch-model`): novo `OutreachTouch`, registro insert-only
  do fato "toque marcado como enviado" (canal, motivo, quando), mesmo
  padrão de `OpportunityStatusChange`. Base de dados pro motor de
  cadência sugerida dos próximos módulos — nunca persiste "próximo
  passo planejado", sempre derivado na leitura. Ver
  `docs/specs/fase-g-outreach-assistido.md`.

- **Proibições determinísticas de urgência falsa e generalização vazia**
  (Fase G, módulo 4 `prompt-prohibition-guards`): subject/body/cta
  são rejeitados (pedindo nova geração) se mencionarem prazo/urgência
  sem data real nos dados, ou generalizarem "clientes como você" sem
  caso concreto (número real) nos dados — nunca bloqueia palavra
  isolada, só a combinação gatilho+ausência do dado que legitimaria.
  Decisões de gatilhos e regras em consulta ao agente Sales Coach. Ver
  `docs/specs/fase-g-outreach-assistido.md`.

- **Tom por status de cliente no rascunho de e-mail** (Fase G,
  módulo 3 `tone-by-customer-status`): o prompt de geração usa uma de
  duas instruções fixas conforme `is_customer` — cliente ativo abre
  citando produto já em uso (proibido mencionar produto não usado na
  abertura) com CTA de continuidade; prospecção fria abre pelo achado
  externo (proibido "percebemos que...") com CTA exploratório de
  baixo compromisso (proibido pedir demo/orçamento/apresentação).
  Decisões de texto em consulta ao agente Outbound Strategist. Ver
  `docs/specs/fase-g-outreach-assistido.md`.

- **Diferencial persuasivo com guard-rails determinísticos** (Fase G,
  módulo 2 `differentiator-and-ps-fields`): `EmailDraft` ganha
  `differentiator`/`ps` opcionais, validados por 5 checagens
  determinísticas (limite de 1 frase, blocklist de superlativos,
  número precisa ter match literal em evidence/portfolio, comparativo
  exige número âncora, sem menção a fonte externa não citada) — campo
  que reprova é descartado, nunca derruba o resto do rascunho.
  Decisões de guard-rail em consulta ao agente Sales Engineer. Ver
  `docs/specs/fase-g-outreach-assistido.md`.

- **Motivo principal no rascunho de e-mail** (Fase G, módulo 1
  `primary-reason-field`, inicia a Fase G): `EmailDraft` ganha
  `primary_reason`, sempre eco do motivo determinístico de entrada
  (`justification`) — a IA nunca decide ou reescreve esse valor, só é
  instruída a reforçá-lo em subject/body/cta. Blindagem provada por
  teste (não só instrução de prompt). Ver
  `docs/specs/fase-g-outreach-assistido.md`.

- **Detecção de mapeamento quebrado** (Fase F, módulo 6
  `mapping-health-check`, fecha a Fase F): quando um campo mapeado é
  removido/renomeado no Salesforce, o Lead.Tracker avisa em vez de
  falhar silenciosamente — badge "Campo removido" na tela de
  mapeamento com a frase de negócio (nunca o nome técnico do campo),
  e o `health_check()` do módulo reporta o problema nos detalhes sem
  nunca marcar o módulo como não-saudável (o sync continua
  funcionando pros demais campos). Decisões de linguagem/severidade
  em consulta ao agente Sales Engineer. Ver
  `docs/specs/fase-f-mapeamento-campo-personalizado.md`.

- **Tela de mapeamento de campo personalizado** (Fase F, módulo 5
  `mapping-config-ui`, única tela desta fase): nova seção em
  Configurações — tabela de campos personalizados do Salesforce com
  dropdown de papel semântico por linha, salvando ao selecionar (sem
  botão "Salvar"), reatribuição automática com aviso quando dois
  campos disputam o mesmo papel. Linguagem 100% de negócio (nunca
  "hint"/termo técnico), decidida em consulta ao agente Sales
  Engineer. Achados de revisão corrigidos: trava de unicidade no
  banco (`provider_id`+`role`) impede dois campos mapeados pro mesmo
  papel sob concorrência; reconciliação de estado no frontend usa
  identificador estável (API name), nunca o rótulo exibido. Ver
  `docs/specs/fase-f-mapeamento-campo-personalizado.md`.

- **Divisão de contexto guiada por mapeamento** (Fase F, módulo 4
  `mapping-driven-context-split`): `/sync` agora aplica os
  `FieldMapping` configurados — campo customizado mapeado sobrescreve
  o campo estrutural correspondente (`industry`/`renewal_date`/novo
  `deal_size_hint`), sempre, mesmo que já houvesse valor; campo sem
  mapeamento continua como contexto bruto (comportamento inalterado
  da Fase A). Só paga o custo de `fetch_context()` quando existe
  mapeamento configurado. Achado de revisão corrigido: valor mapeado
  agora fica disponível pro motor de regras na mesma rodada de sync
  em que foi promovido, não só na próxima. Decisões técnicas em
  consulta ao agente Salesforce Architect. Ver
  `docs/specs/fase-f-mapeamento-campo-personalizado.md`.

- **Papel semântico e armazenamento de mapeamento de campo** (Fase F,
  módulos 2 `semantic-field-role` e 3 `field-mapping-store`): novo
  enum `SemanticFieldRole` (`industry_hint`/`deal_size_hint`/
  `renewal_date`, sem valor "raw_context" — ausência de mapeamento já
  é o comportamento padrão) e config `FieldMapping` por instalação
  (id determinístico, upsert por `provider_id`+`source_field_api_name`,
  mesmo padrão de `ICPProfile`/`RepTarget`). Ver
  `docs/specs/fase-f-mapeamento-campo-personalizado.md`.

- **Catálogo de campos personalizados do Salesforce** (Fase F, módulo 1
  `sobject-field-catalog`, inicia a Fase F): novo método
  `SalesforceProvider.describe_custom_account_fields()`, via
  `sobjectDescribe` do Account, lista campos personalizados
  (`custom=True AND updateable=True`) com nome/rótulo/tipo — base pra
  a futura tela de mapeamento campo→papel semântico, sem exigir que o
  usuário digite API name. Cache em memória por instância com TTL de
  1h (describe é uma chamada pesada, conta pro limite diário da org),
  com bypass explícito via `force_refresh`. Decisões técnicas em
  consulta ao agente Salesforce Architect. Ver
  `docs/specs/fase-f-mapeamento-campo-personalizado.md`.

- **Exportação da prospecção geográfica** (Fase E, módulo 8
  `geo-export`, fecha a Fase E): botões "PDF"/"Excel" na tela de
  resultado do wizard, reaproveitando 100% o exportador já existente
  de Oportunidades — nenhum código de exportação novo, só um
  mapeamento de `GeoDiscoveryItem` pro formato de linha já suportado.
  Ver `docs/specs/fase-e-prospeccao-geografica.md`.

- **Cards de resultado da prospecção geográfica** (Fase E, módulo 7
  `geo-results-view`): `POST /geo-discovery/run` agora devolve as 3
  listas completas (`promoted`/`deferred`/`rejected`), não só
  contagens — cada item traz categoria (bate/não bate com o critério),
  avaliação/reviews, endereço e score, ordenados por compatibilidade
  decrescente. Wizard troca a tabela simples por cards visuais com
  barra de compatibilidade; resultados fora do critério ficam atrás de
  um toggle "Ver todos os resultados", ocultos por padrão. Decisão
  explícita do agente Sales Engineer contra mapa embutido nesta fatia.
  Nenhuma lógica de scoring/promoção/cota alterada. Revisão de código
  aprovada sem achados Críticos/Importantes. Ver
  `docs/specs/fase-e-prospeccao-geografica.md`.

- **Wizard de prospecção geográfica** (Fase E, módulo 6 `icp-wizard-ui`
  — fecha a esteira geográfica ponta a ponta): novo assistente de 4
  passos (rep+produto → endereço+raio → revisar sugestão → confirmar e
  buscar), fluxo desenhado em consulta ao agente Sales Engineer.
  `POST /geo-discovery/run` orquestra `discover()` → `score_place_signal`
  → `select_promotions` → persiste só os promovidos como
  `Company`/`Opportunity` reais. Resultado em linguagem comercial
  ("Prontos para contato" / "Na fila para amanhã" / "Fora do critério"),
  nunca termos técnicos. Revisão de código corrigiu um bug real (cota
  diária comparando data local do servidor contra `created_at` em UTC) e
  documentou um TOCTOU de baixo risco aceito conscientemente. Ver
  `docs/specs/fase-e-prospeccao-geografica.md`.

- **Trava anti-spam de prospecção geográfica** (Fase E, módulo 5
  `anti-spam-promotion-gate`): `select_promotions` decide quais sinais
  geográficos pontuados (módulo 4) viram `Company`/`Opportunity` real —
  score mínimo de 0.75 e cap de 20 promoções por representante/dia
  (ambos configuráveis via `GET`/`PUT /settings/config/geo-promotion`),
  decididos em consulta ao agente Outbound Strategist. Busca nunca é
  bloqueada pela cota — excedente elegível vira `deferred` (evidência
  suficiente, só sem cota agora), distinto de `rejected` (evidência
  insuficiente, nunca vira registro). Ver
  `docs/specs/fase-e-prospeccao-geografica.md`.

- **Pontuação determinística de sinal geográfico** (Fase E, módulo 4
  `geo-scoring-rules`): `score_place_signal` pontua `PlaceSignal` (módulo
  2) em 3 camadas — `business_status` fechado é descarte determinístico
  (`None`, tipo de retorno diferente de score baixo); categoria bate/não
  bate; `rating`/`review_count` como bônus fraco que nunca inverte a
  hierarquia. Hierarquia e pesos decididos em consulta ao agente Outbound
  Strategist. `BUSINESS_STATUS_UNSPECIFIED` (achado da revisão de código)
  tratado como "não sabemos", nunca como fechado. Ver
  `docs/specs/fase-e-prospeccao-geografica.md`.

- **Derivação automática de critério de ICP** (Fase E, módulo 3
  `icp-auto-derivation`): `GET /icp-suggestion` deriva `industry_hint`
  (moda de `Company.industry` entre clientes satisfeitos) e
  `company_size_hint` (moda de `Company.segment`) a partir de
  `is_customer=true` + `opportunity_score >= 0.7` — threshold, amostra
  mínima (5) e regra de moda decididos em consulta ao agente Growth
  Hacker. `None` (nada pra derivar) é distinto de `confidence="low"`
  (sugestão real com poucos dados, nunca escondida). Nunca auto-aplica
  no `ICPProfile` — só o usuário confirma no wizard futuro. Ver
  `docs/specs/fase-e-prospeccao-geografica.md`.

- **Coleta de sinal do Google Places** (Fase E, módulo 2
  `places-signal-collector`): `GoogleMapsProvider` implementado e ligado
  em `SOURCES` (Configurações de Fontes). `discover(origin_address,
  radius_km, place_category)` geocodifica a origem e busca lugares
  próximos, devolvendo sinal bruto (`PlaceSignal`: categoria,
  business_status, rating, contagem de reviews) — nunca decide
  oportunidade. Decisão de arquitetura: não participa do `/sync`
  periódico (`fetch_companies()` sempre `[]` de propósito) — a busca é
  sob demanda, futuramente disparada pelo wizard (módulo 6). Origem
  geográfica vem de `ICPProfile.search_origin_address` (endereço
  cadastrado manualmente, decisão confirmada com o usuário). Endpoints
  confirmados via fonte oficial do Google (Geocoding API + Places API
  New). Ver `docs/specs/fase-e-prospeccao-geografica.md`.

- **Armazenamento de critério de ICP** (Fase E, módulo 1
  `icp-profile-store`): `GET`/`PUT /icp-profile` guardam produto de
  referência, categoria do Google Places, porte-alvo e raio de busca —
  configuração singleton por instalação, sem taxonomia fechada (núcleo
  genérico). `GET` antes do primeiro `PUT` nunca retorna 404. Primeiro de
  8 módulos do capability map da Fase E (Plan consultado, confirmado pelo
  usuário) — ver `docs/specs/fase-e-prospeccao-geografica.md`.

- **Campos padrão adicionais de Account do Salesforce** (Fase A): `Company`
  ganha `industry`, `annual_revenue`, `employee_count`, `address`
  (objeto aninhado city/state/postal_code/country). Consultei o agente
  Salesforce Architect antes de desenhar o modelo (decisão registrada em
  `docs/specs/salesforce-account-standard-fields.md`): `industry` fica
  distinto de `segment` (vertical de mercado vs. categorização comercial
  própria); `Type`/`CreatedDate` do Salesforce ficam conscientemente fora
  de escopo (redundante com `is_customer`/sem consumidor ainda). Revisão
  de código encontrou um bug real (`merge_pair` usando `or` pra campo
  numérico — `0` é falsy em Python, sobrescreveria `annual_revenue=0.0`/
  `employee_count=0` legítimos), corrigido antes deste commit.

- **Campos personalizados do Salesforce como contexto bruto** (Fase A):
  `SalesforceProvider.fetch_context()` traz os campos `__c` da conta via
  SOQL `FIELDS(CUSTOM)`, guardados sem interpretação em
  `ProviderContext.extra["custom_fields"]` — nunca vira regra de
  oportunidade nem passa por IA nesta fase, só deixa o dado pronto pra
  quando o pipeline de IA real existir. Org sem nenhum campo personalizado
  (`MALFORMED_QUERY`) nunca gera erro. Ver
  `docs/specs/salesforce-custom-fields-context.md`.

- **Dashboard consome todo o dado da Fase D** (Fase D, módulo 8 — fecha a
  fase): cards de KPI ganham linha de explicação (potencial ponderado
  avaliado/estimado, oportunidades zumbi, triagem atrasada, e os 8 cards
  já existentes); novas seções "Alcance do funil" (nunca "conversão"),
  cortes por representante/segmento/fonte, e "Cobertura de meta por
  representante" com seletor mensal/trimestral. Revisão de código
  encontrou 3 bugs de estado no React (erro que travava o dashboard
  permanentemente após uma falha transitória, resposta desatualizada
  podendo sobrescrever a mais recente ao trocar de período rápido, e
  o dashboard inteiro sumindo a cada troca de período) — todos
  corrigidos antes deste commit. Ver
  `docs/specs/fase-d-dashboard-acionavel.md`.

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
