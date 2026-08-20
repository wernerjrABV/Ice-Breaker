# CoolCare MVP — desenho da solução

## Objetivo

Demonstrar um agente de triagem de manutenção para coolers e geladeiras. O responsável do ponto de venda (PDV) conversa por uma interface semelhante ao WhatsApp, executa somente verificações simples e seguras, e recebe uma resolução remota ou um encaminhamento completo ao fornecedor de manutenção.

O MVP prova que a triagem pode reduzir visitas evitáveis sem substituir o fornecedor nem permitir instruções de reparo de risco.

## Escopo funcional

O atendimento é iniciado de forma proativa a partir de um chamado já aberto. O chamado contém somente o nome do PDV, o assunto e uma descrição breve.

A primeira mensagem é:

> Olá! Recebi um chamado do **{nome do PDV}** sobre **{assunto}**. Quero entender melhor o que está acontecendo e verificar se já consigo ajudar você agora. Você está próximo ao equipamento?

Se o PDV estiver próximo, o agente pede uma foto da etiqueta ou o número de série. A leitura da etiqueta é obrigatória na jornada; caso a confiança de leitura seja baixa, o agente solicita o serial manualmente. O modelo/serial identificado é confirmado antes do diagnóstico.

O MVP cobre somente coolers e geladeiras e os seguintes sintomas:

| Sintoma | Encaminhamento esperado |
|---|---|
| Congela bebidas | Checklist remoto para ajuste de temperatura e condições de uso. |
| Porta não fecha | Checklist remoto para obstrução, organização interna e vedação visivelmente deslocada; se persistir, encaminha ao fornecedor. |
| Não gela | Checklist remoto de ventilação, porta, ajuste e gelo visível; se persistir, encaminha ao fornecedor. |
| Não liga | Verificação externa segura; se continuar sem ligar, encaminha ao fornecedor. |
| Ruído anormal | Registra evidência e encaminha ao fornecedor. |
| Cheiro de queimado, faísca, cabo danificado ou vazamento | Encaminhamento urgente ao fornecedor e orientação para não manipular o equipamento. |

O agente nunca orienta abertura do equipamento, reparo elétrico ou manipulação de componentes internos.

## Decisão e confirmação

A solução é híbrida:

- O agente de IA conduz a conversa, interpreta texto, lê a etiqueta e elabora o resumo do atendimento.
- Regras determinísticas decidem os casos de segurança e a rota de encaminhamento.

Após concluir um checklist remoto, o agente pergunta se o cooler voltou a funcionar corretamente.

- Com confirmação **sim**, o ticket é encerrado como `resolvido_remotamente`. Somente esse status é elegível à medição de visita evitada.
- Com confirmação **não**, o caso passa para `encaminhado_fornecedor`.
- Sem resposta por 30 minutos, o caso passa automaticamente para `encaminhado_fornecedor`, com a indicação `sem_confirmacao_pdv`.
- Um caso crítico é encaminhado imediatamente; não espera a confirmação ou o timeout.

## Arquitetura

O projeto reutiliza o template `ABI-HACKATHON-SAZ`:

```text
React (chat do PDV)
  → FastAPI + SQLite (estado, persistência e timeout)
  → API do agente CrewAI (conversa, leitura de etiqueta e contexto)
  → regras locais de triagem (decisão segura)
```

### Front-end

Uma única página imita um chat de WhatsApp. Ela exibe a mensagem proativa, respostas rápidas, campo de texto, upload de foto e o status do atendimento. Não há integração real com WhatsApp no MVP.

### Back-end

O FastAPI persiste o atendimento em SQLite, recebe mensagens e imagens, chama o agente e aplica as regras de decisão. Ao entrar em `aguardando_confirmacao`, grava o horário limite. Uma rota de verificação simples identifica atendimentos vencidos e cria o encaminhamento ao fornecedor. A demo pode chamar essa rota explicitamente; não requer agendador externo.

### Agente

O CrewAI recebe o contexto do chamado e a mensagem atual. Ele identifica/valida o equipamento, faz uma pergunta por vez, usa uma base local de instruções seguras e retorna dados estruturados para o back-end. Dados do hackathon são locais: catálogo de equipamentos, tickets resumidos, sintomas e roteiros.

## Dados e contratos

| Entidade | Campos essenciais |
|---|---|
| `ticket` | `id`, `nome_pdv`, `assunto`, `descricao_base`, `status`, `criado_em` |
| `equipamento` | `modelo`, `numero_serie`, `foto_etiqueta`, `confianca_leitura` |
| `triagem` | sintomas, respostas, ações orientadas, classificação e justificativa |
| `resultado` | `resolvido_remotamente` ou `encaminhado_fornecedor` |
| `confirmacao` | resposta do PDV, horário da pergunta, limite de 30 minutos e motivo de timeout |
| `encaminhamento_fornecedor` | PDV, equipamento, evidências, ações tentadas e motivo do encaminhamento |

## Cenários de demonstração e aceitação

1. **Congela bebidas:** identificação por etiqueta, ajuste seguro, confirmação positiva e `resolvido_remotamente`.
2. **Porta não fecha:** checklist remoto e confirmação positiva ou encaminhamento se o problema persistir.
3. **Não liga:** verificação externa segura e `encaminhado_fornecedor`.
4. **Cheiro de queimado:** interrupção imediata e encaminhamento urgente ao fornecedor.
5. **Sem resposta:** checklist concluído, vencimento de 30 minutos e `encaminhado_fornecedor` com `sem_confirmacao_pdv`.

## Fora do escopo

- Integração real com Delfos, WhatsApp, sistema de tickets ou fornecedor.
- Agendamento real de visita.
- Outros equipamentos, como chopper ou postmix.
- Treinamento de modelo próprio.
- Cálculo financeiro de saving sem confirmação positiva do PDV.

## Métricas demonstradas

O dashboard/resultado do MVP deve deixar visível o desfecho do atendimento e registrar visitas evitadas apenas em casos confirmados. A narrativa de benefício usa o baseline fornecido: 14.324 tickets com potencial de resolução remota em três meses, custo médio de BRL 200 e cenários anuais de captura de 50% (BRL 5,73 milhões) e 60% (BRL 6,88 milhões).
