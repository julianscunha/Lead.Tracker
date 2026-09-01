# 13 — Resiliência, Erros e Observabilidade

## Objetivo

O usuário será majoritariamente leigo. Erros técnicos devem ser convertidos em mensagens claras e acionáveis.

## Categorias

- configuração;
- autenticação;
- conectividade;
- timeout;
- limite de API;
- integração;
- dados inválidos;
- IA;
- exportação.

## Exemplo

Nunca mostrar:

```text
requests.exceptions.ConnectionError
```

Mostrar:

```text
Não foi possível conectar ao Salesforce.

Verifique a conexão com a internet e as credenciais configuradas.
```

## Tratamento

Toda integração deve capturar exceções e devolvê-las como erros de domínio amigáveis.

## Timeout

Toda chamada externa deve possuir timeout explícito.

## Retry

Usar retry somente para erros transitórios.

Não repetir:
- credencial inválida;
- requisição inválida;
- autorização negada.

## Limites de API

Informar:
- serviço;
- motivo;
- ação recomendada.

## Logs

Logs técnicos ficam disponíveis na área de Logs.

Secrets nunca devem aparecer nos logs.

## Degradação controlada

Uma integração opcional indisponível não deve derrubar todo o módulo.

Exemplo:

```text
IA indisponível
→ oportunidades determinísticas continuam disponíveis.
```

## Operação

A interface deve informar:
- progresso;
- etapa atual;
- sucesso;
- falha parcial;
- conclusão.

Nunca deixar uma tela sem feedback durante operação longa.
