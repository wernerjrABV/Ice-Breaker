# Abertura de Chamado e Atualizações Internas — Design

## Objetivo

Permitir iniciar o atendimento do zero em uma tela de abertura simples e
tornar visíveis, dentro da conversa, as atualizações operacionais do agente.
O demonstrador usa um PDV fixo; a pessoa informa somente um assunto livre.

## Escopo

- tela inicial para abrir um chamado com um único campo de texto;
- primeira triagem automática, executada logo após a persistência;
- mensagens internas em amarelo e mensagens trocadas com o PDV em branco;
- continuidade da triagem existente quando há contato pelo WhatsApp;
- mensagens internas explícitas nos três desfechos: fornecedor, solução
  remota e continuidade com fornecedor após tentativa remota;
- testes de backend e frontend para as novas transições e apresentação.

Não entram no escopo: integração real com WhatsApp, autenticação, mudança do
motor de diagnóstico posterior, nem alteração dos chamados `DEMO-*`.

## Experiência

`App` passa a expor uma rota inicial de abertura (`/` ou `/tickets/new`) e
mantém `/home?ticketId=...` como a experiência de acompanhamento. A página
inicial exibe o cartão **Abrir chamado**, contendo o campo obrigatório
`Descreva o chamado` e o botão **Enviar para triagem**.
O PDV persistido é sempre `PDV Demonstração`; `descricao_base` recebe o mesmo
texto do assunto e o equipamento padrão continua `cooler`.

Depois do envio bem-sucedido, a URL passa a conter o ID retornado e a tela de
conversa é apresentada. Cada mensagem possui uma origem pública:

| Origem | Fundo | Rótulo acessível | Uso |
|---|---|---|---|
| interna (`role=internal`) | amarelo claro | `Atualização interna` | automações e decisões operacionais; não é comunicação ao PDV |
| externa (`role=assistant`) | branco | `Mensagem para o PDV` | textos enviados pelo agente ao WhatsApp/PDV |
| externa (`role=user`) | branco | `Resposta do PDV` | mensagens inseridas pelo usuário durante a simulação |

O rótulo fica visível e é lido por tecnologia assistiva; cor nunca é o único
indicador. As mensagens de checklist, confirmação e resolução enviadas pelo
agente mantêm `role=assistant`; a mensagem digitada mantém `role=user`. A interface
não mostra o compositor, ações rápidas, foto ou serial depois de um estado
terminal.

## Primeira triagem automática

O backend grava primeiro a atualização interna **Enviado ao agente para
primeira triagem**. A decisão usa regras locais determinísticas sobre o
assunto normalizado, para que a demonstração seja repetível e não dependa de
uma chamada ao modelo.

O chamado vai diretamente ao fornecedor quando o assunto contiver um sinal
de risco já suportado (`cheiro de queimado`, `faísca`, `vazamento` ou `cabo
danificado`) ou uma solicitação explícita de fornecedor/visita/troca. Nesse
caso, o backend grava **Enviado para o fornecedor**, finaliza o chamado como
`encaminhado_fornecedor` e não envia mensagem ao PDV.

Para os sintomas seguros e tratáveis remotamente já reconhecidos (`congela
bebidas`, `porta não fecha` e `não gela`), o chamado precisa de contato: o
backend grava **Iniciou conversa com o PDV**, mantém o status `em_triagem`,
inicia em `aguardando_proximidade` e acrescenta a primeira mensagem externa
já usada pelo fluxo atual. Demais assuntos são encaminhados normalmente ao
fornecedor por não possuírem um roteiro remoto seguro. Palavras de risco
mantêm a prioridade urgente e prevalecem sobre qualquer outra regra.

Assuntos fora do escopo conservam a resposta 422 já existente e não criam um
chamado parcial.

## Fluxo e transições

```text
Assunto livre
  -> [interna] Enviado ao agente para primeira triagem
  -> fornecedor/riscos: [interna] Enviado para o fornecedor -> finalizado
  -> contato: [interna] Iniciou conversa com o PDV
             -> [cliente] abertura/triagem existente
             -> solução: [interna] Solução encontrada pelo agente
                          -> [cliente] Problema corrigido; chamado encerrado
             -> sem solução: [interna] Não encontrou solução; atendimento seguirá com o fornecedor
                            -> finalizado
```

`_route_supplier` centraliza todos os encaminhamentos. Antes da mensagem
externa de orientação de fornecedor que já existe para a conversa em
andamento, ele adiciona a atualização interna de acordo com o motivo:

- primeira triagem sem contato: `Enviado para o fornecedor`;
- falha após checklist/negação de confirmação/timeout: `Não encontrou solução; atendimento seguirá com o fornecedor`;
- risco identificado durante conversa: a mesma segunda mensagem, preservando
  a prioridade urgente.

Na confirmação positiva, antes da mensagem final ao PDV, o serviço registra
`Solução encontrada pelo agente`. A mensagem externa final passa a declarar
explicitamente que o problema foi corrigido e que o chamado está fechado.

## Contrato e persistência

`TicketMessage.role` passa a aceitar `internal`, além dos valores semânticos
existentes `assistant` e `user`. A interface usa `internal` para distinguir o
amarelo; todos os outros papéis são externos e recebem fundo branco. O banco
continua armazenando mensagens na tabela atual; nenhuma migração estrutural é
necessária. `_agent_reply` deve excluir mensagens internas do payload enviado
ao agente para que notas operacionais jamais virem contexto de conversa.

`kind` ganha `internal_status`. `POST /tickets` mantém integralmente o
contrato atual para compatibilidade. O frontend novo usa `POST /demo/tickets`,
cujo request contém exclusivamente `assunto`; o serviço fixa o PDV e os
demais valores demonstrativos. Nenhuma integração de WhatsApp é chamada: a
conversa é uma representação visual do canal.

Eventos auditáveis existentes permanecem a fonte do painel à direita. A
primeira triagem acrescenta eventos públicos novos à taxonomia:

- `initial_triage_started`;
- `initial_triage_routed_supplier`;
- `pdv_conversation_started`;
- `remote_solution_found`.

Se necessário, esses eventos recebem somente `reason`, `priority` e
`requires_pdv_contact`; nunca o texto integral do assunto.

## Implementação prevista

Backend: adicionar o endpoint demonstrativo sem romper o endpoint atual;
ampliar enums/modelos de mensagem e evento; extrair a decisão de primeira
triagem em helper puro; alterar `create_case`, `_route_supplier` e o
encerramento positivo para acrescentar atualizações internas; filtrar essas
mensagens do payload do agente e preservar o contrato dos endpoints atuais.

Frontend: criar `NewTicketPage`/`NewTicketForm` e registrar a rota inicial;
remover a criação automática do ticket de demonstração ao montar `Home`;
simplificar o cliente para criação demonstrativa; renderizar classes por
origem, sem o balão verde atual; ajustar os cards terminais para não duplicar
nem contradizer as novas mensagens de linha do tempo.

## Tratamento de erro

O formulário bloqueia assunto vazio e exibe o erro de criação sem navegar.
Erro de rede ou 422 mantém o texto digitado. A falha do agente atual durante
uma conversa não cria uma atualização de sucesso nem encerra o chamado. Um
chamado já finalizado continua rejeitando novas mensagens, fotos e serial com
409.

## Testes e aceite

Backend:

- criação por assunto normal gera a atualização de primeira triagem, inicia
  contato e preserva a abertura ao PDV;
- assunto de risco e solicitação explícita de fornecedor finaliza sem mensagem
  ao PDV;
- confirmação positiva produz a atualização de solução antes da mensagem de
  fechamento ao PDV;
- negação, timeout e risco posterior produzem a atualização de ausência de
  solução antes do encaminhamento;
- notas internas nunca chegam ao payload enviado ao agente; mensagens externas
  preservam os papéis `assistant` e `user`.

Frontend:

- tela sem ticket cria o chamado usando apenas o assunto e navega para o ID;
- mensagens internas recebem rótulo/classe amarela; mensagens ao PDV e do PDV
  recebem apresentação branca e rótulos corretos;
- estados terminais bloqueiam novos envios; erros preservam o assunto;
- os testes existentes de chat e painel continuam passando.

Aceite visual: o apresentador consegue demonstrar, a partir de uma página
vazia, tanto o caminho direto ao fornecedor quanto o caminho WhatsApp até
resolução ou retorno ao fornecedor, sem intervenção manual para escolher a
primeira decisão.
