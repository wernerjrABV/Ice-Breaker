# Dashboard de Acompanhamento do Agente — Design

## Objetivo

Criar uma visão de apresentação para acompanhar um chamado individual em tempo quase real, exibindo lado a lado a conversa do PDV e os eventos auditáveis que explicam o processamento do CoolCare. O dashboard deve tornar visíveis as etapas, regras, sinais, decisões e impacto financeiro do atendimento sem expor prompts, credenciais ou raciocínio interno bruto do modelo.

## Escopo

O trabalho cobre:

- painel de acompanhamento do chamado atual integrado à tela existente;
- persistência de eventos estruturados por chamado;
- endpoint REST incremental para leitura dos eventos;
- polling no frontend a cada 1 segundo;
- métricas de etapa, OCR, prioridade e economia;
- comportamento responsivo e resiliente a falhas temporárias;
- eventos das transições existentes de criação, risco, identificação, diagnóstico, checklist, espera e encerramento.

Não fazem parte deste escopo:

- dashboard agregado de vários chamados;
- WebSocket ou Server-Sent Events;
- métricas históricas ou relatórios gerenciais;
- exposição de prompts, tokens, chain-of-thought ou respostas brutas do modelo;
- alteração do valor fixo de R$ 200 usado na demonstração;
- autenticação ou autorização novas para o MVP local.

## Decisões de experiência

### Layout

Em telas desktop, a página usa duas colunas:

- coluna esquerda: experiência atual do chat do PDV em uma moldura compacta;
- coluna direita: painel `CoolCare Intelligence`, com métricas, impacto financeiro, decisão em foco, linha do tempo e sinais da decisão.

Em telas menores que 900 px, as seções passam para uma coluna, com o chat antes do painel. O chat mantém seus controles, estados finais, timeout e tratamento de erros atuais.

### Hierarquia do painel

O painel contém:

1. Cabeçalho com ID do chamado e indicador de atualização.
2. Métricas de etapa, confiança OCR e prioridade.
3. Card de economia.
4. Decisão em foco, derivada do evento mais recente.
5. Linha do tempo cronológica dos eventos.
6. Sinais consolidados: sintoma, risco, equipamento, serial e desfecho.

### Economia

O custo evitável da demonstração permanece fixo em R$ 200 por chamado.

- Enquanto o chamado estiver ativo, o card mostra `Economia potencial — R$ 200` e `Ainda não contabilizada`.
- Quando o status for `resolvido_remotamente`, mostra `Economia realizada — R$ 200`.
- Quando o status for `encaminhado_fornecedor`, mostra `Economia não realizada — R$ 0`.
- A economia é derivada exclusivamente do status retornado pelo backend, nunca de um evento intermediário.

## Arquitetura

O backend continua sendo a fonte de verdade do chamado. Cada ponto relevante do serviço grava um evento estruturado na mesma transação lógica da alteração que representa. Os eventos ficam persistidos no SQLite e são consultados por um endpoint incremental.

O frontend mantém o carregamento atual do `Ticket` e inicia um polling independente de eventos depois de conhecer o ID do chamado. A cada 1.000 ms, pede somente registros com ID maior que o último recebido. O painel acrescenta os registros em ordem e deriva sua apresentação do histórico e do `Ticket` atual.

```text
Interação do PDV
      │
      ▼
FastAPI / service.py ──► altera chamado e registra ticket_event
      │                                      │
      ▼                                      ▼
GET /tickets/{id}                  GET /tickets/{id}/events?after=N
      │                                      │
      └──────────────► Home + AgentDashboard ◄┘
```

## Persistência

### Tabela `ticket_events`

| Coluna | Tipo | Regras |
|---|---|---|
| `id` | INTEGER | chave primária autoincremental |
| `ticket_id` | TEXT | obrigatório, referência ao chamado |
| `category` | TEXT | obrigatório, enum público do evento |
| `title` | TEXT | obrigatório, texto curto em português |
| `description` | TEXT | obrigatório, explicação auditável e segura |
| `state` | TEXT | obrigatório: `completed`, `active`, `waiting`, `warning` ou `failed` |
| `metadata_json` | TEXT | objeto JSON com campos públicos permitidos |
| `created_at` | TEXT | timestamp UTC ISO 8601 |

Um índice composto em `(ticket_id, id)` sustenta a consulta incremental. A exclusão/recriação dos chamados fixos de demonstração também exclui/recria seus eventos; chamados fora da lista de demo permanecem intocados.

### Contrato público

```json
{
  "id": 17,
  "ticket_id": "DEMO-REMOTE",
  "category": "triage_decision",
  "title": "Checklist remoto selecionado",
  "description": "O sintoma congela bebidas permite verificações seguras no PDV.",
  "state": "completed",
  "metadata": {
    "symptom": "congela_bebidas",
    "outcome": "checklist_remoto",
    "priority": "normal"
  },
  "created_at": "2026-08-25T17:32:09Z"
}
```

`metadata` aceita apenas valores JSON simples e listas de strings. Não recebe mensagem integral do usuário, prompt, resposta bruta de LLM, chave, token ou stack trace.

## Taxonomia inicial de eventos

| Categoria | Momento | Metadados permitidos |
|---|---|---|
| `ticket_created` | chamado persistido | `equipment_type` |
| `scope_validated` | equipamento dentro do escopo | `equipment_type` |
| `risk_evaluated` | avaliação determinística de risco | `detected`, `risk_flags` |
| `stage_changed` | mudança de etapa da conversa | `from_stage`, `to_stage` |
| `agent_requested` | backend solicita intenção estruturada | `stage` |
| `agent_interpreted` | intenção estruturada validada | `reply_key`, `symptom`, `risk_flags` |
| `ocr_completed` | leitura de etiqueta concluída | `model`, `serial`, `confidence`, `manual_required` |
| `equipment_confirmed` | PDV confirma identificação | `model`, `serial`, `confidence` |
| `triage_decision` | motor determinístico decide o caminho | `symptom`, `outcome`, `priority`, `reason` |
| `checklist_sent` | checklist seguro persistido e enviado | `actions` |
| `confirmation_waiting` | janela de confirmação iniciada | `deadline` |
| `ticket_resolved` | confirmação positiva do PDV | `reason`, `saving_brl` |
| `supplier_routed` | encaminhamento normal ou urgente | `reason`, `priority` |
| `confirmation_expired` | timeout da confirmação | `reason`, `priority` |

Eventos que descrevem ações concluídas usam `completed`. A espera pela confirmação usa `waiting`; risco ou encaminhamento urgente usa `warning`; falha controlada de integração pode usar `failed`. O painel não cria eventos sintéticos para preencher lacunas.

## API

### `GET /tickets/{ticket_id}/events`

Parâmetros:

- `after`: inteiro opcional, padrão `0`, deve ser maior ou igual a zero;
- `limit`: inteiro opcional, padrão `100`, mínimo `1`, máximo `200`.

Resposta `200`:

```json
{
  "items": [],
  "last_id": 0,
  "terminal": false
}
```

Regras:

- retorna somente eventos cujo `id > after`, ordenados por `id` crescente;
- `last_id` é o maior ID retornado ou repete `after` quando não houver itens;
- `terminal` é verdadeiro quando o chamado está em `resolvido_remotamente` ou `encaminhado_fornecedor`;
- chamado inexistente retorna `404`;
- `after` ou `limit` inválido retorna `422` pelo FastAPI.

O contrato suporta paginação: se uma resposta vier com `items.length === limit`, o frontend busca a próxima página imediatamente antes de retomar o intervalo normal.

## Registro dos eventos

O módulo de banco oferece uma única função:

```python
record_ticket_event(
    ticket_id: str,
    category: str,
    title: str,
    description: str,
    state: str,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]
```

O serviço chama essa função somente depois que a operação representada foi validada. Os pontos de registro ficam próximos às transições atuais em `service.py`, mas textos e metadados públicos são construídos por helpers dedicados para manter consistência e impedir vazamento de dados internos.

Uma falha ao persistir evento deve falhar a operação do chamado antes de enviar resposta de sucesso. Para garantir consistência, as funções de banco que alteram estado e registram o respectivo evento usam uma transação SQLite única. Eventos meramente informativos ligados a leituras do agente são registrados em transações próprias e nunca substituem o tratamento atual de erro da integração.

## Frontend

### Componentes

- `AgentDashboard`: contêiner do painel e composição dos dados.
- `AgentMetrics`: etapa, confiança OCR, prioridade e economia.
- `DecisionTimeline`: eventos em ordem cronológica, com estados visuais.
- `DecisionSignals`: resumo dos metadados seguros mais recentes.
- `useTicketEvents`: polling incremental, paginação, deduplicação e reconexão.

`Home` permanece responsável pela criação e atualização do chamado. Ele entrega `ticket.id`, `ticket.status`, `ticket.stage`, `ticket.priority` e `ticket.equipment` ao painel. O hook mantém os eventos separados do estado do chat para que uma falha de observabilidade não bloqueie a conversa.

### Polling

- começa apenas quando existe `ticketId`;
- executa uma busca imediata e depois a cada 1.000 ms;
- nunca mantém duas requisições concorrentes;
- cancela timers e ignora respostas antigas ao trocar de chamado ou desmontar;
- deduplica itens por `id`;
- busca páginas adicionais imediatamente quando atingir o limite;
- encerra o polling depois de receber `terminal: true` e esvaziar todas as páginas;
- em falha, preserva os eventos e tenta novamente após 1 s, 2 s, 4 s e então 5 s nas tentativas seguintes;
- após uma resposta bem-sucedida, volta ao intervalo de 1 s.

### Estados visuais

- carregamento inicial: skeleton discreto no painel;
- sem eventos: mensagem `Preparando acompanhamento do agente...`;
- conectado: indicador `Agente ativo`;
- após falha: indicador `Reconectando`, sem apagar conteúdo;
- terminal: indicador `Atendimento concluído`, sem novas consultas;
- categoria desconhecida: item genérico com título e descrição fornecidos pela API.

Animações respeitam `prefers-reduced-motion`. Títulos, estados, valores e indicadores não dependem apenas de cor. A linha do tempo usa uma região com nome acessível e os eventos são uma lista semântica.

## Tratamento de erros e segurança

- Falhas no endpoint de eventos não alteram nem bloqueiam o chat.
- A UI não mostra stack trace, URL interna ou conteúdo bruto de erro.
- O backend valida categoria, estado e formato dos metadados antes de persistir.
- O endpoint serializa apenas o contrato público.
- Eventos não armazenam texto integral do usuário, foto, prompt ou saída bruta do agente.
- O nome do arquivo da etiqueta só aparece no `Ticket` atual; o log recebe apenas modelo, serial e confiança necessários à apresentação.

## Estratégia de testes

### Backend

- criação, serialização e ordenação dos eventos;
- filtro `after`, limites e paginação;
- `404` para chamado inexistente;
- limpeza restrita aos IDs fixos da demonstração;
- evento correto para criação, risco urgente, OCR confiante, OCR incerto, confirmação do equipamento, checklist, resolução, encaminhamento e timeout;
- atomicidade entre transição de estado e evento correspondente;
- ausência de mensagem, prompt e resposta bruta nos metadados públicos.

### Frontend

- cliente interpreta o contrato do endpoint;
- polling começa após obter o ID e envia o último ID recebido;
- não há chamadas concorrentes;
- páginas cheias são drenadas antes do próximo intervalo;
- falha mantém eventos e aplica backoff limitado a 5 s;
- polling termina no estado terminal;
- categoria desconhecida não quebra a renderização;
- economia potencial, realizada e não realizada seguem exclusivamente o status;
- layout contém chat e dashboard lado a lado no desktop e mantém nomes acessíveis.

### Verificação integrada

O roteiro `DEMO-REMOTE` deve mostrar a progressão completa até `Economia realizada — R$ 200`. O roteiro `DEMO-URGENT` deve interromper a triagem, destacar risco e mostrar `Economia não realizada — R$ 0`. O reset deve permitir repetir ambos sem acumular eventos antigos.

## Critérios de aceite

1. A apresentação acompanha um chamado individual ao lado do chat.
2. Cada item mostrado na linha do tempo corresponde a um evento persistido pelo backend.
3. Novos eventos aparecem em até 2 segundos em condições locais normais.
4. Recarregar a página recompõe todo o histórico do chamado.
5. Uma falha temporária do painel não impede o atendimento.
6. O dashboard nunca exibe prompts, chain-of-thought, credenciais ou respostas brutas do modelo.
7. R$ 200 só é contabilizado quando o chamado termina como `resolvido_remotamente`.
8. Encaminhamento normal, urgente ou por timeout contabiliza R$ 0.
9. Os quatro chamados fixos continuam reiniciáveis pelo roteiro da demonstração.
10. Testes, lint e build existentes continuam aprovados.
