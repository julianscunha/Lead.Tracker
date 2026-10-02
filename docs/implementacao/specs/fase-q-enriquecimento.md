---
title: "Fase Q — Enriquecimento de porte e setor por API configurável"
order: 40
tags: [lead-tracker, implementacao, spec]
---

# Fase Q — Enriquecimento de porte e setor por API configurável

Status: **concluída**.

## Problema

Muitas empresas chegam ao Lead.Tracker só com nome e site (Google Maps, planilha). Sem **setor** (`industry`) e **porte** (`employee_count`), a leitura da conta fica pobre. Hoje esses campos só vêm do CRM ou do CSV. Quem contrata uma API de dados de empresas (qualquer uma) não tem como usá-la.

## O que é (e o que não é)

- **É:** um provider único e genérico, "API HTTP JSON configurável", que dado o domínio da empresa consulta a API que o **operador** configurou e preenche `industry` e `employee_count` quando estão vazios.
- **Provider só coleta e normaliza:** não calcula score, não usa IA, não decide oportunidade (contrato de `providers/base.py`). Devolve uma `Company` parcial.
- **Não é:** um conector de fornecedor específico, nem leitura de dado de pessoas, nem dado que entre sem rastro: o que a API traz passa pela reconciliação da Fase N (nunca vence em silêncio).

## Decisões

**Por que genérico.** O núcleo é aberto e não embute fornecedor (CLAUDE.md). O operador informa o endereço da API com `{domain}`, o nome do cabeçalho da chave e **onde** estão porte e setor no JSON (caminho com pontos, ex.: `metrics.employees`). Qualquer API que responda JSON serve; trocar de fornecedor é só mudar a configuração.

**Por que sob demanda e não no sync.** O `/sync` busca de fontes que listam empresas; aqui é uma consulta **por empresa**, paga e com limite de uso. Rodar sozinho gastaria cota sem o operador ver, e uma API lenta atrasaria a atualização de tudo. Por isso é um botão ("Completar porte e setor"), com lote de até 50 (limite 1 a 200), prazo total e resumo do resultado. O provider devolve listas vazias no `fetch_companies` (como website e Google Maps).

**Configuração** (`SourceDescriptor` + chaves no `.env-model`): `ENRICHMENT_ENABLED`, `ENRICHMENT_URL_TEMPLATE`, `ENRICHMENT_AUTH_HEADER`, `ENRICHMENT_API_KEY` (secreta), `ENRICHMENT_MAP_EMPLOYEES`, `ENRICHMENT_MAP_INDUSTRY`. Tudo editado pela tela, nunca à mão.

**Quem é consultado.** Empresas com site próprio válido e `industry` **ou** `employee_count` vazio. O domínio sai de `normalize_domain`, é revalidado (nome de domínio, nunca IP) e codificado na URL; plataformas genéricas (Facebook, Instagram, Linktree…) são puladas. Só a empresa que precisa de dado é consultada.

**Normalização.** `employee_count`: só inteiro maior que zero (número ou texto numérico "120"); **faixa ("51-200") vira vazio**: nada de ponto médio inventado. `industry`: texto, espaços normalizados, máximo 100 caracteres, sem `<`/`>` nem caractere de controle. Todo outro campo do JSON é descartado na hora.

**Reconciliação (Fase N, sem máquina nova).** `reconcile(..., "enrichment", fields=("industry","employee_count"))`: campo vazio é preenchido com origem `enrichment`; valor de CRM/manual/CSV que a API contesta abre um **conflito** e o atual é mantido; valor escolhido pelo usuário em mapeamento nunca é contestado; um valor já recusado não reabre. A gravação usa `save_company` e `record_reconciliation` (auditoria `sync:enrichment`, sem texto livre pessoal) sob o `SYNC_LOCK`, porque a empresa é gravada por inteiro.

**Resposta da rota.** `POST /enrichment/run?limit=50` devolve `{enriquecidas, sem_dado, conflitos, erros[]}`. Fonte desligada ou sem configuração é erro de domínio com ação ("ligue e configure em Entrada de dados").

**Erros e resiliência.** Timeout de 10 s por chamada e prazo total de 120 s para o lote. 429, 5xx e falha de rede: **uma** nova tentativa após espera curta. 401/403: erro de autenticação e o **lote para** (insistir só gera bloqueio). 404: "sem dado". Outro 4xx: a empresa é pulada, sem nova tentativa. Mensagens em português, sem exceção técnica. Falha da API nunca derruba o módulo.

## Segurança e LGPD

- **Rede:** toda chamada passa por `core/safe_fetch.fetch_page` (resolve DNS, só IP público, conecta no IP validado, sem proxy do ambiente, teto de bytes, só `application/json`). O novo parâmetro `extra_headers` leva a chave **só ao host da primeira URL**: nunca a um redirect para outro host (nem ao par www/sem www).
- **Chave:** só em https e só no cabeçalho, nunca na URL, em log, erro, `GET /settings`, exportação nem prompt de IA. O nome do cabeçalho é validado e não pode ser `Host`/`User-Agent`.
- **Template:** `{domain}` exatamente uma vez e nunca dentro do nome do servidor (o domínio de um lead não escolhe para onde a chamada vai).
- **Dado:** o JSON bruto nunca é gravado, logado nem enviado à IA. O produto não lê nem guarda dado de pessoas por esta fonte: só setor e número de funcionários da **empresa**. O teste da conexão usa um domínio fixo de teste e mostra os valores lidos.
- **Limite aceito:** `safe_fetch` só aceita portas 80/443 e nomes de domínio públicos; APIs em porta diferente ou em rede interna não são suportadas.

## UI

Em Entrada de dados: o card **Enriquecimento de empresas (porte e setor)** aparece pelo descritor (liga/desliga, campos, "Testar conexão"). Na seção de atualização, o botão **"Completar porte e setor (até 50 empresas)"**, com uma dica explicando que usa a API configurada, só preenche o que está vazio, divergências viram conflito e não lê dado de pessoas. Mostra o resumo (completadas, sem dado novo, divergências, avisos). Os conflitos aparecem na tela existente de Oportunidades.

## Fora de escopo

Ação por empresa (um botão na linha da empresa); faixa de funcionários (hoje vira vazio); `annual_revenue`; enriquecimento automático no sync; vários fornecedores ao mesmo tempo; API com autenticação por OAuth ou por parâmetro de URL; portas diferentes de 80/443.

## Teste

API sempre simulada, só empresas fictícias (`tests/test_enrichment_http.py`, `tests/test_routes_enrichment.py`, `tests/test_safe_fetch.py`):

- **Leitura e tipos:** caminho com pontos; faixa vira vazio; texto numérico vale; campos extras descartados; caminho ausente vira vazio.
- **Domínio:** domínio estranho recusado sem chamar a API; domínio genérico pulado; template inválido recusado.
- **Erros:** 401 interrompe o lote; 429 tenta uma vez; 404 conta "sem dado"; outro 4xx pula a empresa; timeout vira erro amigável; resposta que não é JSON ou grande demais.
- **Reconciliação:** preenche vazio com origem `enrichment`; abre conflito contra CRM mantendo o atual; respeita `mapping`; não duplica conflito aberto.
- **Vazamento:** a chave nunca aparece em log, erro, `GET /settings` nem na URL; `extra_headers` não acompanha redirect para outro host.

## Critério de sucesso

- [x] Com a API configurada, "Completar porte e setor" preenche setor e número exato de funcionários só onde estavam vazios.
- [x] Nenhum valor de outra fonte é sobrescrito em silêncio: divergência vira conflito para o usuário.
- [x] A chave nunca sai do cabeçalho de uma chamada ao host configurado, e nada de pessoa é lido ou guardado.
