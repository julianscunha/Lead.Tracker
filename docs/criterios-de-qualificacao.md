# Critérios de qualificação de oportunidade

Este documento explica **o que cada critério significa, de onde vem o
dado e por que o número/corte é esse** — pra quem usa o Lead.Tracker
entender como o sistema chegou naquele score, naquela banda ou naquele
selo, sem precisar abrir código. Não é uma spec técnica de
implementação (essas ficam em `docs/specs/`, uso interno de
desenvolvimento).

Todo critério listado aqui é uma **regra determinística**, nunca uma
estimativa de IA: o sistema segue uma fórmula fixa e auditável, nunca
"acha" ou inventa um valor. Os números de corte (dias, multiplicadores,
bandas) são revisáveis com o tempo — cada um vem acompanhado do porquê,
pra ficar claro quando faz sentido ajustar.

## Recência de atividade → confiança da oportunidade

**O que é:** mede o quão "viva" está a conversa com aquela conta. Duas
oportunidades tecnicamente idênticas não têm o mesmo peso se uma conta
está em silêncio há muito tempo — a oportunidade continua existindo, mas
a chance de avançar agora é menor. Isso ajusta o `confidence_score`
(confiança) da oportunidade, nunca o fato de ela existir ou não.

**De onde vem o dado:** a data da última atividade registrada no
Salesforce daquela empresa. Fontes que não têm esse conceito (cadastro
manual, planilha) deixam esse dado em branco — nesse caso a empresa é
tratada como a categoria mais fria (ver tabela abaixo), nunca como um
terceiro estado "não sei".

**Os 3 níveis:**

| Nível | Janela desde a última atividade | Efeito na confiança |
|---|---|---|
| Quente | até 120 dias | Sem penalidade |
| Morno | de 121 a 270 dias | Reduz 15% |
| Muito frio | mais de 270 dias, **ou nunca registrado** | Reduz 50% |

**Por que esses números:** ciclos de venda de infraestrutura de TI
costumam rodar 90-180 dias ou mais — uma conta parada 60-90 dias entre
reuniões por causa de aprovação de orçamento ou processo de compra é
normal, não significa que esfriou. Um corte curto demais penalizaria
esse ritmo normal como se fosse desengajamento. Por outro lado, tratar
"91 dias sem contato" e "700 dias sem contato" como a mesma coisa também
distorce a priorização — por isso existe o nível intermediário "morno"
em vez de um corte único.

Esses números são o ponto de partida, não uma constante definitiva: o
ideal é calibrá-los pela mediana real de intervalo entre atividades dos
negócios que sua equipe já fechou, quando esse histórico existir.

**Regra importante:** a ausência da data de última atividade nunca vira
um terceiro estado "desconhecido" — conta sem essa informação é tratada
como muito fria, de propósito. Prefere subestimar a confiança a fingir
neutralidade sobre um dado que falta.

## Nível hierárquico do contato

**O que é:** indica se o contato registrado na oportunidade é quem
decide (ex.: diretor, gestor) ou só um influenciador técnico. Uma
oportunidade forte cujo único contato conhecido é operacional carrega um
risco a mais: pode nunca chegar em quem aprova a compra.

**De onde vem o dado:** inferido automaticamente a partir do cargo
registrado no Salesforce, por reconhecimento de palavra-chave em
português — **sem uso de IA**, é busca direta de termos conhecidos:

| Classificação | Palavras reconhecidas no cargo |
|---|---|
| Decisor | gestor, diretor, gerente, head, ceo, cto, cio |
| Influenciador técnico | arquiteto, especialista |
| Operacional | técnico, analista, suporte |

Cargo sem nenhuma dessas palavras fica **sem classificação** — o sistema
nunca inventa um nível quando não reconhece o termo.

**Limitação atual:** ainda não existe uma tela pra corrigir manualmente
essa classificação quando ela erra (ex.: cargos incomuns, em outro
idioma, ou ambíguos como "Diretor de Operações"). Por enquanto, a
classificação automática é a única fonte — a correção manual é um
recurso planejado.

## Quantificação de gap por severidade

**O que é:** classifica o quão sério é um problema/lacuna detectado
(ex.: "cliente não tem proteção de backup"), sem nunca calcular um valor
em reais automaticamente — o sistema nunca inventa quanto custa a
inação, isso sempre fica como pergunta pro vendedor confirmar junto ao
cliente.

**De onde vem o dado:** **100% preenchido manualmente** pelo vendedor na
tela da oportunidade — não existe hoje nenhuma fonte automática que
avalie isso. Dois campos, sempre escolhidos de uma lista (nunca digitado
livre):

- **Alcance** — o quanto da base do cliente é afetado: `Isolado` (poucos
  sistemas/licenças), `Parcial` (parte relevante do parque), ou
  `Generalizado` (maior parte do parque).
- **Criticidade** — o quão grave é se o problema se concretizar:
  `Não crítico` (impacto operacional baixo), `Crítico interno` (grave,
  mas não visível pro cliente final), ou `Crítico e exposto` (afeta
  produção ou algo que o cliente do seu cliente vê diretamente).

Um terceiro campo, **Observação**, é opcional — espaço de texto livre
pra registrar o motivo/contexto da classificação, serve de lembrete pra
quando a oportunidade for revisada depois.

**Como vira uma banda:** os dois campos se combinam numa tabela fixa,
sempre a mesma, nunca ajustada por IA:

| | Não crítico | Crítico interno | Crítico e exposto |
|---|---|---|---|
| Isolado | Baixo | Médio | Alto |
| Parcial | Médio | Alto | Alto |
| Generalizado | Médio | Alto | **Crítico** |

Enquanto qualquer um dos dois campos não for preenchido, a banda aparece
como **"Não avaliado"** — o sistema nunca calcula uma banda com
informação incompleta.

**Por que só 2 perguntas e não mais:** o objetivo é dar ao vendedor um
jeito rápido de sinalizar prioridade sem virar um formulário longo.
Alcance e criticidade juntos já bastam pra separar "vale a pena tratar
com urgência" de "fica pra depois" — outros fatores (prazo, orçamento,
quem decide) já têm campo próprio em outros lugares da oportunidade.

## Saúde da conta e cadência de revisão sugerida

**O que é:** com que urgência vale revisar uma conta — em vez de um
calendário fixo ("revisar toda conta a cada 90 dias"), o sistema sugere um
prazo específico por conta, combinando três informações: a saúde atual da
conta, quanto falta pra renovação do contrato (quando essa data existe) e
quantos sinais de risco/expansão ainda estão em aberto.

**De onde vem a saúde da conta ("Saudável" / "Atenção" / "Crítica" /
"Dados insuficientes"):** sempre o pior entre dois indicadores, nunca uma
média (uma média deixaria passar um problema sério escondido atrás de um
número bom) — nunca preenchida manualmente, sempre recalculada na leitura:

- **Recência de atividade** — mesma régua de quente/morno/muito frio já
  usada na confiança da oportunidade (ver seção acima).
- **Confiança média das oportunidades em aberto daquela conta** — alta
  (≥70%), média (40-69%) ou baixa (abaixo de 40%).

Conta sem nenhuma oportunidade em aberto **e** sem nenhuma atividade
registrada cai em **"Dados insuficientes"** — o sistema nunca assume que
uma conta está saudável só porque não há informação nenhuma sobre ela.

**Por que a contagem de sinais abertos não entra na saúde:** um sinal de
risco/expansão em aberto (`CompanySignal` — renovação próxima, troca de
contato-chave, etc.) já entra como uma informação separada na tabela de
cadência (próximo parágrafo). Contar o mesmo sinal duas vezes — uma na
saúde, outra na cadência — inflaria artificialmente a urgência.

**Como vira "revisar em X dias":** tabela fixa cruzando saúde × prazo até a
renovação (até 30 dias / 31 a 120 dias / 121 a 270 dias / sem data
cadastrada ou mais de 270 dias). Conta com saúde crítica sempre pede
revisão imediata ou quase; conta saudável com renovação próxima tem a
revisão alinhada à própria data de renovação (nunca um número solto
desconectado do calendário real do contrato); conta saudável sem renovação
próxima cai numa cadência de rotina mais espaçada. **2 ou mais sinais em
aberto** empurram a conta pra uma linha mais urgente da tabela, qualquer
que seja a saúde.

**De onde vem a data de renovação:** hoje é 100% preenchida manualmente na
tela da oportunidade (nenhuma fonte automática traz isso ainda) — conta sem
essa data preenchida simplesmente não usa a parte "alinhada à renovação" da
lógica, cai só na combinação saúde + sinais abertos.

## Os números não são definitivos

Todo threshold e toda fórmula deste documento é revisável — nada aqui é
"assim porque sim". Se um critério não estiver refletindo a realidade do
seu negócio na prática (ex.: 120 dias parecer curto ou longo demais pro
seu ciclo de venda), isso é sinal de que vale revisar o número, não de
que o sistema está errado por natureza. Este documento existe justamente
pra deixar claro o raciocínio por trás de cada corte, facilitando essa
revisão.
