# Roadmap — Lead.Tracker

Documento de decisões e faseamento, pra qualquer pessoa (ou agente) continuar
o desenvolvimento sem quebrar a arquitetura já validada. Cada fase depende da
anterior; não pular fase só porque parece mais interessante.

Origem: sessão de planejamento com 10 personas especializadas (Salesforce
Architect, Pipeline Analyst, Deal Strategist, Account Strategist, Outbound
Strategist, Sales Engineer, Data Consolidation Agent, Discovery Coach,
Proposal Strategist, Sales Outreach) revisando o domínio atual do
Lead.Tracker. Convergência entre elas nos princípios abaixo — não é opinião
de uma só.

## Princípios que atravessam todas as fases

Isso vale mais que qualquer item de fase individual — se uma decisão de
implementação violar um destes, pare e repense a implementação, não o
princípio.

1. **Núcleo sempre genérico.** Nenhuma fase pode hardcodar nome de campo,
   fabricante, produto ou categoria específica de um cliente do Lead.Tracker.
   Tudo que varia entre instalações vira dado de configuração (papel
   semântico, categoria, `relation_type`, `signal_type` como enum aberto) —
   nunca lógica de código. Já é regra do `CLAUDE.md`; as 6 personas
   reforçaram isso de ângulos diferentes sem eu pedir.

2. **Evidência é fato + implicação de negócio + fonte + data**, sempre.
   Nunca um log técnico cru ("Produto X ausente"). Formato de referência:
   `"[FATO] ... → [RISCO/OPORTUNIDADE] ... → [FONTE] ..., sincronizado em ..."`.
   Vale para toda oportunidade nova daqui pra frente, incluindo as geradas
   por sinais de expansão (Fase C) e prospecção geográfica (Fase E).

3. **Os 4 números da oportunidade nunca colapsam em um só.**
   `opportunity_score`, `financial_potential`, `strategic_score`,
   `confidence_score` continuam distintos no modelo de dados. Onde for
   preciso desempatar/ordenar (dashboard, fila do vendedor), o critério
   é: `confidence_score` desempata antes de `financial_potential` bruto —
   mas isso é regra de **exibição/ordenação**, nunca um campo novo persistido
   tipo "deal score" agregado.

4. **Interface pensada pra operador não-técnico.** Este é um requisito
   explícito do usuário do projeto, vale para todas as fases com tela nova
   (D, E, F):
   - Nunca expor nome de campo de API (`Segmento_Cliente__c`) na UI — sempre
     rótulo em português, escolhido de uma lista/dropdown, nunca digitado.
   - Nunca pedir pro usuário entender o que é SOQL, OAuth, `signal_type` ou
     qualquer termo técnico interno — esses termos existem só no código.
   - Assistente guiado (passo a passo com confirmação) em vez de tela de
     configuração com muitos campos soltos — mesmo padrão que a tela de
     portfólio já usa (Adicionar/Sobrescrever, revisão antes de aplicar).
   - Todo número/score na tela precisa de uma explicação inline (tooltip ou
     texto de apoio) do que ele significa e de onde veio — nunca um número
     sozinho sem contexto.
   - Estado vazio/erro sempre em linguagem de negócio ("Não consegui
     confirmar os dados dessa conta no Salesforce — verifique o acesso nas
     Configurações"), nunca a mensagem técnica crua (já é regra do
     `CLAUDE.md`, reforçando aqui pro contexto de UI).

5. **Resultado visual, chamativo, sempre exportável.** Outro requisito
   explícito do usuário: quem opera é o time comercial, público muito
   visual — número solto em tabela cinza não é aceitável onde já existe
   alternativa gráfica.
   - Toda tela que mostra resultado de análise (Dashboard, Oportunidades,
     e as novas de ICP/Prospecção) usa gráfico onde fizer sentido (já é o
     padrão do Dashboard atual — donut por fabricante, barras de potencial),
     não só linha de tabela.
   - **Gerar relatório é obrigatório em toda tela de resultado, não só um
     "nice to have"**: Dashboard e Oportunidades já têm isso
     (`executive_pdf`, `opportunities_pdf`/`opportunities_excel` em
     `exports/`) — qualquer tela nova que mostre resultado de análise (ICP/
     Prospecção na Fase E, por exemplo) precisa nascer com exportação
     equivalente, seguindo o mesmo padrão, não como pendência posterior.
   - Isso não conflita com o princípio 4 — "visual e chamativo" e "número
     sempre explicado" andam juntos, não são opostos.

## Fases

### Fase 0 — Configurações de Fontes
**Pré-requisito de tudo.** Sem essa tela, ligar o Salesforce hoje exige
editar `.env` na mão — contraria a própria regra do projeto ("usuário
configura tudo por tela, nunca editando `.env` na mão", `CLAUDE.md`
"Configuration"). Identificada tarde nesta sessão de planejamento porque
ficou implícita ("a tela de configuração de fontes já cogitada") sem nunca
virar item formal — corrigindo aqui.

- **Uma tela só, lista de fontes**: Salesforce, Website, Google Maps,
  Manual — cada uma com uma chave liga/desliga (`SALESFORCE_ENABLED` etc.,
  já existem no `.env-model`).
- **Formulário de credencial por fonte, em português, sem jargão técnico**:
  nada de "Client ID"/"Client Secret" crus — rótulo tipo "Identificador do
  Aplicativo Conectado" com um texto de apoio curto e link pra doc de como
  gerar isso no Salesforce. Mesma régua do princípio 4 (operador não-técnico).
- **O próprio toggle já sinaliza o estado da conexão, sem precisar de mais
  um clique**: ao ligar a fonte, o sistema chama `test_connection()` (que
  cada provider já implementa — `SalesforceProvider` já tem isso pronto)
  automaticamente em seguida, e mostra um indicador discreto ao lado do
  toggle — um ponto colorido + rótulo curto: 🟢 "Conectado", 🔴 "Sem
  conexão", ⚪ "Verificando...". Nunca deixa o toggle "ligado" sem dizer se
  aquilo realmente funcionou.
  - Ao reabrir a tela depois, o indicador reflete o último `health_check()`
    conhecido daquela fonte (o módulo já tem esse hook), não fica sempre
    "verificando" do zero.
  - Clicar no indicador (ou um botão "Testar de novo") repete o teste sob
    demanda, pro caso de o usuário ter corrigido a credencial e querer
    confirmar sem precisar desligar/ligar o toggle.
  - Mensagem de erro sempre em linguagem de negócio ("Não consegui
    confirmar o acesso — verifique o Identificador e a Chave"), nunca a
    exceção técnica crua.
- **Peça de arquitetura nova, não só UI**: hoje `sync_env()` só adiciona
  chave ausente ao `.env`, nunca atualiza uma já existente — não existe
  ainda um jeito de a tela *gravar* o valor que o usuário digitou. Precisa
  de uma rota tipo `PUT /settings` que escreve no `.env` a partir da tela,
  respeitando o mesmo princípio de nunca sobrescrever silenciosamente algo
  que o usuário não mudou.
- Secrets nunca aparecem em texto puro depois de salvos — campo de senha
  mascarado, nunca reexibido em claro na tela (mesma regra de "segredo
  nunca aparece em log/erro/export" aplicada aqui).

### Fase A — Ingestão ampliada do Salesforce
**Status:** concluída (specs: `docs/specs/salesforce-custom-fields-context.md`,
`docs/specs/salesforce-account-standard-fields.md`).
**Depende da Fase 0** pra ter como configurar credenciais sem editar `.env`
na mão — mas o provider em si já foi implementado e testado antes dessa
lacuna ser percebida; a spec/código de ingestão não muda, só a forma como o
usuário final liga isso.

- [x] Campos padrão adicionais de `Account`: endereço (`BillingCity/State/PostalCode/Country`
  — sem `BillingStreet` por ora, custo de PII sem ganho de precisão de geocoding),
  `Industry`, `AnnualRevenue`, `NumberOfEmployees`, `LastActivityDate`. `Type`/`CreatedDate`
  conscientemente fora de escopo (redundante com `is_customer`/sem consumidor ainda —
  ver `docs/specs/salesforce-account-standard-fields.md`).
- [x] Campos personalizados (`__c`) como contexto bruto via `FIELDS(CUSTOM)` —
  guardado, não interpretado.
- **Adiado para depois da Fase B, não desta fase:** dados de `Opportunity`/
  `OpportunityLineItem` existentes no CRM do cliente (histórico de compra) —
  é sinal de alto valor, mas depende do modelo de proveniência de sinal da
  Fase B pra não virar dado solto sem rastreabilidade.
- **Sem tela nova nesta fase** — é só ingestão, dado ainda não aparece pro
  usuário além do que já aparece (contexto bruto pra uso futuro de IA).

### Fase B — Fundação do modelo de dados
**Por que antes da UI/regras novas:** retrofitar histórico depois que dado
real começar a fluir é caro — não dá pra reconstruir "quando essa oportunidade
mudou de status" se não foi guardado desde o início.

- Histórico de transição de status (`stage_entered_at` por mudança, não só
  status atual) — pré-requisito de qualquer métrica de tempo parado/velocity.
- `rep_id`/responsável em `Company` e `Opportunity` — pré-requisito de
  qualquer corte "quem está performando".
- Segmentação: porte (a partir de `AnnualRevenue`/`NumberOfEmployees` já
  trazidos na Fase A), região (a partir do endereço da Fase A).
- Proveniência do sinal: qual fonte/regra gerou aquela oportunidade
  (`Opportunity` herda `sources` como a `Company` já faz) — necessário pra
  medir qualidade de sinal por fonte na Fase D.
- `category` em `Product`/`Service` — pré-requisito da Fase C (regra "tem
  categoria backup, não tem categoria monitoring").
- `relation_type` (`prerequisite`/`complementary`/`substitute`, string
  livre por convenção — implementado como `Product.related_services:
  list[ProductRelation]`, renomeado de `related_service_ids: list[str]` já
  que o campo nunca teve consumidor real ainda) — sem tabela nova.
- Modelo genérico de sinal (`CompanySignal`/`ExpansionSignal`): `signal_type`
  como string aberta, não enum fechado no código — feed pro mesmo motor de
  regras da Fase C, nunca um motor paralelo.
- **`trigger_event`/recência de mudança em `Company`/`Opportunity`** — sem
  saber *o que mudou recentemente* (contratação, expansão, incidente,
  renovação próxima), não existe "por que agora" pro vendedor. É o campo de
  maior alavancagem apontado na revisão de descoberta — mais barato e mais
  genérico que qualquer sinal específico de fabricante.
- **Papel do contato na oportunidade, em `Contact`**: além do cargo já
  capturado, sinalizar (mesmo que de forma genérica: "operações/TI",
  "compliance/risco", "liderança executiva") quem provavelmente sente o
  impacto de cada tipo de gap — não é a mesma pessoa que reporta o dado
  técnico.
- **`attempted_solutions`/histórico de tentativa anterior em `Company`**
  (mesmo que só um sinal — ferramenta descontinuada detectada, downgrade,
  volume de chamado de suporte) — sem isso o sistema não tem como sugerir
  "o que já tentaram e por que não resolveu".
- **`strategic_context` (texto livre, com fonte e data) em `Company`** —
  espaço pra registrar iniciativa/objetivo estratégico já mencionado pela
  empresa (ex.: em release, site, CRM) — sempre com evidência, nunca
  inferido pela IA sem fonte.
- **Sem tela nova nesta fase** — é só schema/modelo, preparação silenciosa.

### Fase B.1 — Ligação real (ingestão → banco → API → frontend)
**Status:** concluída (spec: `docs/specs/fase-b1-ligacao-real.md`). Rodou
sem gerar oportunidade por regra de propósito — não existe ainda
persistência de regra (isso é a Fase C, próxima). Achado real ao validar
em ambiente com banco de instalação anterior à Fase B: `create_all` não
adiciona coluna a tabela já existente, então um install com dado de antes
da Fase B quebra com "no such column" até o schema ser recriado — confirma
a dívida já documentada em `core/db.py`/spec da Fase B, não uma surpresa
nova; sem Alembic ainda por decisão consciente.

**A lacuna mais antiga desta conversa, identificada no início e nunca
formalizada até agora.** Hoje `backend/main.py` só tem `/ping` e rotas de
export — nenhuma rota lê/escreve `Company`/`Opportunity` de verdade, e o
frontend roda inteiro sobre `sampleData.ts`/`sampleMetrics.ts` (dado
fictício fixo no código). Nenhuma fase anterior faz sentido pro usuário
final sem esta — é o fio que liga tudo que já existe isolado e testado.

- Rota de sincronização (`POST /sync` ou botão "Atualizar dados" na tela de
  Fontes da Fase 0): aciona o(s) provider(s) habilitado(s) →
  `normalization.py` (dedup) → `portfolio.py` (compara contra portfólio) →
  `opportunity_engine.py` (gera oportunidades) → `repository.py` (persiste
  no SQLite) — o pipeline inteiro já existe em partes isoladas e testadas,
  só falta orquestrar em sequência.
- Rotas de leitura reais: `GET /companies`, `GET /opportunities` (com
  filtros equivalentes aos que a tela já usa), servindo do banco via
  `repository.py` — não mais dado calculado na hora a partir de nada.
- Frontend: `App.tsx`/`Dashboard.tsx` trocam `sampleOpportunities`/
  `sampleMetrics` por `fetch` real nessas rotas (mesmo padrão que
  `api.ts` já usa pra export/e-mail) — inclui estado de carregamento e
  vazio ("nenhuma oportunidade ainda — rode uma sincronização") em
  linguagem de negócio (princípio 4).
- **Sem essa fase, Fases C/D/E não têm dado real pra mostrar** mesmo depois
  de prontas — por isso vem antes de qualquer uma delas, não depois.

### Fase C — Motor de regras ampliado
**Status:** concluída (spec: `docs/specs/fase-c-motor-de-regras.md`).
Depende da Fase B e da Fase B.1 (precisa de dado real fluindo pelo pipeline
pra uma regra nova ter o que avaliar).

- Regra por categoria, não só item-a-item (generaliza `CorrelationRule`
  atual sem trocar sua forma — usa `category` da Fase B).
- Regra de incompatibilidade/consolidação usando `relation_type=substitute`
  → gera oportunidade de tipo `consolidation`, discurso diferente de
  cross-sell simples.
- Regra de pré-requisito usando `relation_type=prerequisite` — sinaliza
  risco técnico se vendido sem o pré-requisito, não só oportunidade.
- Sinais de expansão (renovação próxima, troca de contato-chave, adoção
  parcial de produto multi-módulo) entrando como `CompanySignal` no mesmo
  motor — nunca uma "segunda inteligência" paralela.
- Sinais granulares de qualificação, todos estruturados (sem IA pra
  extrair): recência de atividade no CRM (proxy de momentum, alimenta
  `confidence_score`), nível hierárquico do contato registrado (proxy de
  autoridade — Economic Buyer vs. influenciador), contagem de contatos
  distintos vinculados à empresa (proxy de multi-threading — 1 contato só é
  risco mesmo com produto forte).
- Cadência de revisão de conta (QBR) sugerida por regra determinística, não
  calendário fixo: tabela `saúde da conta × janela de renovação × nº de
  sinais abertos → dias sugeridos pra revisão` (mesmo padrão "regra, não
  mágica" das outras regras desta fase). Ex.: saúde vermelha → revisão
  imediata; saúde verde + renovação em 120 dias → QBR agora, alinhado à
  renovação.
- Só 3 tipos de regra no total (presença/ausência, categoria, relação
  tipada) — resistir a pedido de motor mais genérico tipo query language.
  A tabela de cadência acima é configuração de regra, não um 4º tipo.
- **Tela nova:** editor de regras do portfólio, mas sempre por formulário/
  dropdown ("SE tenho [categoria: backup] E NÃO tenho [categoria:
  monitoring] ENTÃO oportunidade de [categoria: monitoring]") — nunca campo
  de texto livre pra regra.
- Evidência de cada oportunidade passa a citar item real + categoria que
  disparou + fonte + data (formato do princípio 2).
- **Quantificação de gap por severidade, nunca por valor em R$ inventado**:
  `escopo` (quantos sistemas/% de licenças afetados, quando o dado
  existir) × `sinal de criticidade` (se a fonte marcar algo como produção/
  cliente-facing) → banda qualitativa (baixo/médio/alto). O valor exato em
  R$ fica sempre como pergunta em aberto na justificativa, nunca como
  número calculado pelo sistema — a IA nunca inventa custo de inação
  (reforça o princípio 2 e o "nunca decide/inventa sozinha" do domínio).
- Cada evidência pode vir acompanhada de uma `discovery_prompt` opcional —
  a pergunta que o vendedor deveria fazer pra confirmar a causa raiz (ex.:
  "por que o DR nunca foi priorizado — decisão consciente ou lacuna não
  percebida?"), nunca a resposta. Ajuda a virar a tela numa preparação de
  descoberta de verdade, não só uma lista de pistas técnicas.

### Fase D — Dashboard acionável
**Status:** concluída (spec: `docs/specs/fase-d-dashboard-acionavel.md`).
Depende da Fase B (sem histórico de status, aging/velocity são impossíveis).

- Funil com taxa de conversão por etapa (não só contagem).
- Aging: oportunidades em `detected` há mais de N dias sem virar
  `qualified`/`dismissed` — alerta de SLA de triagem configurável.
- Potencial financeiro ponderado por `confidence_score`, exibido ao lado do
  potencial bruto (nunca substituindo, princípio 3).
- `dismissed` com motivo categorizado (sem evidência / sem fit / cliente não
  qualificado / falso positivo de regra) — retroalimenta ajuste de regras.
- Cortes por rep, segmento, fonte de origem — usando os campos da Fase B.
- **Meta/cobertura por rep-período**: sem meta configurada, "potencial
  financeiro total" é número sem contexto. Adicionar cadastro simples de
  meta por rep/segmento/período (manual, não vem de fonte externa) pra
  calcular `coverage ratio`. Rep sem meta configurada mostra "sem meta
  definida", nunca 0% ou divisão por zero.
- **Arquitetura de agregação — decisão de fundo, não detalhe de implementação:**
  o dashboard lê de uma tabela de **snapshot diário** (`opportunity_id,
  snapshot_date, stage, potencial, rep_id, segmento`), recalculada quando o
  motor de regras roda — nunca em tempo real a partir das tabelas
  transacionais a cada request. Isso evita reescrever histórico quando um
  rep muda de território (atribuição fica travada no snapshot do dia) e
  garante que MTD/YTD sejam agregações da mesma tabela, nunca 3 cálculos
  divergentes.
- **Blindagens obrigatórias no agregador** (evitam número bonito mas
  enganoso): excluir/marcar oportunidades "zumbi" (paradas há muito tempo
  no mesmo estágio) de qualquer métrica de "pipeline saudável"; nunca gerar
  novo `opportunity_id` quando uma oportunidade `dismissed` é reaberta
  (senão conta duas vezes no funil histórico); sempre segmentar por
  fonte/porte antes de mostrar um agregado total (misturar contas grandes
  do Salesforce com PME do Maps sem segmentar distorce a média).
- **UI:** todo card de KPI com uma linha de explicação do que aquele número
  significa (princípio 4) — o público final é comercial, não analista de
  dados.

### Fase E — Prospecção geográfica (Google Maps)
**Status:** concluída (spec: `docs/specs/fase-e-prospeccao-geografica.md`).
Depende do endereço já vindo na Fase A.

- Tela de ICP: critérios guardados como dado de configuração por instalação
  (categoria Maps, porte, raio, produto de referência), nunca como schema —
  com opção de **derivar automaticamente** dos próprios clientes satisfeitos
  (`is_customer=true` + `opportunity_score` alto) em vez de o usuário
  preencher tudo do zero.
- Sinais do Places em camadas: categoria batendo com o perfil de referência
  (mais forte) → `business_status=OPERATIONAL` (descarte determinístico de
  fechados) → contagem/nota de reviews como proxy de porte (mais fraco,
  nunca decide sozinho).
- Trava anti-spam: descoberta geográfica cai em `detected` como qualquer
  outra oportunidade — só sai de lá com evidência suficiente. Score mínimo
  configurável antes de "promover" a prospect de verdade. Cap de contatos
  por lote/dia por rep.
- **UI:** assistente de 3-4 passos (produto de referência → raio → revisar
  critério sugerido automaticamente → confirmar) — não uma tela de filtros
  técnicos.
- Resultado da descoberta mostrado como mapa/lista visual (não tabela crua)
  + exportação equivalente à de Oportunidades (PDF/Excel) desde o primeiro
  release desta fase — princípio 5, time comercial precisa levar essa lista
  pra uma reunião sem precisar pedir print pra alguém técnico.

### Fase F — Mapeamento configurável de campo personalizado
Depende da Fase A (contexto bruto já chegando) e reaproveita a mesma tela de
configuração de fontes já cogitada antes desta sessão de planejamento.

- Descoberta assistida via `sobjectDescribe` do Salesforce — lista os campos
  personalizados disponíveis com rótulo e tipo, nunca pede pra digitar API
  name.
- Usuário associa campo personalizado → papel semântico (enum fechado e
  genérico no core: `industry_hint`, `deal_size_hint`, `renewal_date`,
  `raw_context`, ...) via dropdown.
- Campo sem mapeamento continua como contexto bruto pra IA (comportamento
  da Fase A), nunca vira regra determinística sozinho.
- Health check do módulo detecta mapeamento quebrado (campo renomeado/
  removido no Salesforce do cliente) e avisa em linguagem de negócio.
- **UI:** tela de configuração com tabela simples (campo do Salesforce →
  dropdown de papel semântico → status), sem exigir entender o que é uma
  API name.

### Fase G — Outreach assistido (e-mail mais persuasivo + cadência sugerida)
Depende só da Fase C (qualidade de evidência/`primary_reason`) — pode rodar
em paralelo às Fases D/E/F, não depende delas.

- **Rascunho de e-mail** (`ai/email_draft.py`) ganha campos opcionais no
  JSON de saída: `primary_reason` (o motivo determinístico principal,
  separado de `justification` livre, pra subject/body/cta reforçarem o
  mesmo motivo em vez de puxar pra lados diferentes), `differentiator`
  (releitura persuasiva do gap, extraída só do que já está em
  evidence/portfolio — nunca fato novo), `ps` opcional (reforça o ponto
  mais forte já citado no corpo).
- Tom do e-mail varia por `is_customer` (campo que já existe): cliente
  ativo abre citando o produto já em uso (prova social interna, CTA de
  continuidade); prospecção fria abre pelo achado externo, CTA de conversa
  exploratória de baixo risco. É um `if` no prompt, não feature nova.
- **Proibições explícitas no prompt** (fecham brechas que a regra atual
  "nunca agressivo" não cobria): nunca mencionar prazo/urgência sem dado
  temporal real em evidence; nunca citar "clientes como você" sem um caso
  concreto nos dados fornecidos — omitir a seção em vez de generalizar.
- **Cadência sugerida, nunca disparo automático**: cliente existente (3
  toques, canal e intervalo sugeridos, motivo novo a cada toque); prospecção
  fria (cap por rep/dia, nunca pula de `detected` pra `contacted` sem ação
  humana). Tela mostra só "próxima ação sugerida" (1 linha) + botão "marcar
  como enviado" — nunca fila de disparo, nunca métrica de "% de sequência
  completa" (isso empurra cultura de volume, contra o espírito consultivo
  do produto).
- **Governança de status**: silêncio total após a cadência sugerida volta a
  oportunidade pra `qualified` (falta de resposta não é desqualificação),
  nunca `dismissed` automaticamente. `dismissed` só por decisão humana
  explícita, com motivo. Qualquer sugestão de mudança de status por regra
  de tempo vira notificação pro usuário decidir, nunca a mudança em si —
  mesmo princípio de "IA nunca decide sozinha" aplicado ao pipeline, não só
  ao envio de e-mail.

## Débito técnico que bloqueia release de produção (não bloqueia dev)

**Migração de schema (Alembic).** Hoje `core/db.py::init_db()` usa
`Base.metadata.create_all()` — cria tabela ausente, mas **nunca adiciona
coluna nova a uma tabela que já existe**. Isso já se provou um problema
real durante o desenvolvimento (Fases B e C adicionaram colunas várias
vezes; cada vez foi preciso apagar e recriar o banco de dev manualmente).

**Por que é aceitável agora e deixa de ser:** aceitável enquanto só existem
bancos de desenvolvimento/teste, sem instalação real com dado de cliente.
Deixa de ser aceitável no momento em que existir a primeira instalação em
produção — a primeira atualização de versão com schema novo depois disso
quebraria com "no such column" sem aviso, sem forma de recuperar o dado já
gravado.

**O que fazer, quando chegar a hora:** o Tech.Forge Core já usa Alembic
(é dependência dele, não uma ferramenta nova pro projeto) — adotar o mesmo
aqui: gerar migração por mudança de schema, `alembic upgrade head` no
`install()`/`enable()` do módulo em vez de `create_all()` puro. Não é uma
fase do produto (não entrega nada pro usuário final), é item de checklist
de `shipping-and-launch` — fazer antes do primeiro release real, não antes
de continuar as fases de feature.

## Fora de escopo (mencionado pelas personas, descartado por ora)

- Scraping de LinkedIn/job postings, sentiment analysis de e-mail — alto
  esforço, baixo ROI enquanto os sinais estruturados (CRM, Maps) ainda nem
  estão implementados.
- "Regra builder" livre (AND/OR arbitrário) — as 6 personas convergem em
  evitar isso; 3 tipos fixos de regra bastam.
- Pontuação combinada única ("deal score" agregado) — o domínio proíbe
  colapsar os 4 números; fica só como ordenação de exibição.
- Campos personalizados de `Contact` (só `Account` por ora) — mudaria o
  contrato `DataProvider` inteiro; se necessário, é spec própria.
- **Custo de inação em R$ calculado pelo sistema** — permanentemente fora de
  escopo, não só "por ora". O valor exato sempre fica como pergunta em
  aberto na justificativa (Fase C), nunca um número que a IA ou uma regra
  determinística calcula sozinha — é a mesma linha vermelha de "nunca
  inventar fato", só que fácil de escorregar porque parece útil.
- Pipeline de streaming/CDC pra atualizar o dashboard em tempo real — o
  motor de regras já roda em lote/sob demanda; snapshot diário (Fase D)
  resolve sem essa complexidade. Reconsiderar só se surgir requisito de
  dashboard "ao vivo" com o motor rodando continuamente.
- Sequenciador automático de e-mail/disparo em lote — o produto é
  explicitamente "sugestão + confirmação humana", nunca "fila de
  outreach automatizada" (Fase G).

## Como usar este documento

Cada fase, quando for a vez de implementá-la, ganha sua própria spec em
`docs/specs/` (como já existe para parte da Fase A) antes de qualquer código
— seguindo `spec-driven-development`. Este roadmap não substitui a spec por
fase, só garante que a ordem e as decisões de fundo não se percam entre
sessões.
