# Estudo de caso — Chatbot de Telemanutenção

> Documento estruturado a partir da página **“Manutenção”** do workspace **CX Tech**, no Microsoft Loop.
>
> **Fonte:** [Microsoft Loop — Manutenção](https://loop.cloud.microsoft/p/eyJ3Ijp7InUiOiJodHRwczovL2FuaGV1c2VyYnVzY2hpbmJldi5zaGFyZXBvaW50LmNvbS8_bmF2PWN6MGxNa1ltWkQxaUlXRmpSbDg1UW5veWNUQlhTRnBXZWt0UlgwbFJXSFF0VERWeVdtbFdZbFpQZEZKWFJsUmtXbEl3WWt0NVkybzRkMDlVZEZKVVRFWnZWMVJyUkZOaFR5MG1aajB3TVVoTVFVTk1RbFZJUWtZelZUUlVWRXhOUWtSWlNraFBRelEzVUZwQlVFOUNKbU05Sm1ac2RXbGtQVEUlM0QiLCJyIjpmYWxzZX0sInAiOnsidSI6Imh0dHBzOi8vYW5oZXVzZXJidXNjaGluYmV2LnNoYXJlcG9pbnQuY29tLzpmbDovci9jb250ZW50c3RvcmFnZS9DU1BfZjQ3ZmMxNjktZjYxYy00NWFiLTg3NjUtNWNjYTQzZjIxMDVlL0RvY3VtZW50JTIwTGlicmFyeS9Mb29wQXBwRGF0YS9VbnRpdGxlZCUyMDIubG9vcD9kPXdhNzgzZWFlY2I2ODI0M2ZlODU3ZmE5OWMzZGZmYjg3NyZjc2Y9MSZ3ZWI9MSZuYXY9Y3owbE1rWmpiMjUwWlc1MGMzUnZjbUZuWlNVeVJrTlRVRjltTkRkbVl6RTJPUzFtTmpGakxUUTFZV0l0T0RjMk5TMDFZMk5oTkRObU1qRXdOV1VtWkQxaUlXRmpSbDg1UW5veWNUQlhTRnBXZWt0UlgwbFJXSFF0VERWeVdtbFdZbFpQZEZKWFJsUmtXbEl3WWt0NVkybzRkMDlVZEZKVVRFWnZWMVJyUkZOaFR5MG1aajB3TVVoTVFVTk1RbGhOTlV0Q01sQkJWbGMzV2tKWlN6YzFTbFJSTmpjM1QwUllKbU05SlRKR0ptWnNkV2xrUFRFbVlUMU1iMjl3UVhCd0puQTlKVFF3Wm14MWFXUjRKVEpHYkc5dmNDMXdZV2RsTFdOdmJuUmhhVzVsY2laNFBTVTNRaVV5TW5jbE1qSWxNMEVsTWpKVU1GSlVWVWg0YUdKdGFHeGtXRTVzWTIxS01XTXlUbTloVnpWcFdsaFpkV015YUdoamJWWjNZakpzZFdSRE5XcGlNakU0V1dsR2FGa3dXbVpQVlVvMlRXNUZkMVl3YUdGV2JuQk1WVlk1U2xWV2FEQk1WWGN4WTJ4d2NGWnRTbGRVTTFKVFZqQmFWVnBHY0ZOTlIwcE1aVmRPY1U5SVpGQldTRkpUVmtWNFIySXhaRlZoTUZKVVdWVTRkR1pFUVhoVFJYaENVVEI0UTFaVmFFTlNhazVXVGtaU1ZWUkZNVU5TUm14TFUwVTVSRTVFWkZGWGEwWlJWREJKSlRORUpUSXlKVEpESlRJeWFTVXlNaVV6UVNVeU1qVXdPR1V3T0RnM0xXUTJOREF0TkRoaE55MWlOamsyTFRVMU1tSTFaR0ptTjJGaVlTVXlNaVUzUkElM0QlM0QiLCJyIjpmYWxzZX0sImkiOnsiaSI6IjUwOGUwODg3LWQ2NDAtNDhhNy1iNjk2LTU1MmI1ZGJmN2FiYSJ9fQ)
>
> **Data da extração:** 24 de agosto de 2026. A página não informa o ano do cronograma citado.

## 1. Resumo executivo

O projeto propõe uma jornada de **Telemanutenção** para reduzir a abertura de chamados por telefone e evitar visitas técnicas que poderiam ser resolvidas por orientação remota. A solução leva verificações simples para o chatbot e, quando elas não bastam, direciona o cliente a um agente N1 especializado, com possibilidade de atendimento por vídeo. Somente os casos não resolvidos seguem para visita física.

Embora a oferta de Manutenção já apresente automação elevada, o projeto não nasceu para melhorar apenas esse percentual. Os motivadores explícitos são:

- reduzir a carga operacional do canal 0800 e dos agentes N1 usados apenas para registrar chamados;
- tratar remotamente ocorrências classificadas como “Orientação de uso”;
- realizar checks prévios e enriquecer o diagnóstico antes de mobilizar uma visita;
- aumentar a resolução no prazo e melhorar a experiência do cliente;
- criar uma jornada escalável, com rollout faseado por região geográfica.

O piloto se inspira no fluxo da Claro, que orienta verificações prévias antes de enviar um técnico. A implementação envolve testes de vídeo com a **Twilio** e conversas com a **Embrasac**, empresa citada como especializada em atendimento remoto de manutenção.

## 2. Problema de negócio

### 2.1 Sobrecarga do atendimento telefônico

- **19% dos tickets de Manutenção são abertos via 0800.**
- Esses chamados não exigem necessariamente um especialista N2.
- Ainda assim, mobilizam em média **10 agentes N1** apenas para registrar tickets por telefone.
- A proposta é migrar esse volume para o chatbot, reduzindo a dependência do 0800 e ampliando o uso do canal digital.

### 2.2 Visitas potencialmente evitáveis

- **13% dos tickets são classificados como “Orientação de uso”.**
- Nesses casos, o técnico frequentemente realiza no local verificações básicas que poderiam ter sido conduzidas remotamente.
- O projeto pretende executar essas verificações antes do despacho de uma visita.

### 2.3 Automação alta, mas resolução ainda insuficiente

O texto corrido da página afirma que a oferta entrega **98% de tickets automatizados**, o segundo melhor resultado entre as ofertas. Um quadro executivo incorporado apresenta **94% de automação**. A diferença sugere cortes, períodos ou definições distintas e precisa ser validada antes de usar o dado como baseline oficial.

O mesmo quadro mostra apenas **45% de “OK no prazo”**, indicando que automatizar a abertura do ticket não garante, por si só, uma resolução rápida ou uma boa experiência para o cliente.

## 3. Indicadores apresentados

Os números abaixo foram transcritos do quadro executivo incorporado à página. As siglas foram mantidas como aparecem na fonte, pois o Loop não fornece glossário.

| Indicador | Valor apresentado | Observação |
|---|---:|---|
| Tickets — 2023 | 178 mil | Volume anual indicado no quadro. |
| Tickets — 2024 | 153 mil | Volume anual indicado no quadro. |
| Tickets — 2025 | 0 mil | Provável placeholder ou dado ainda não carregado; requer validação. |
| FTEs | 16 | Associado ao custo operacional apresentado. |
| Custo de FTEs | R$ 1.812.480,00 | Período de referência não informado. |
| Automação — quadro | 94% | Diverge dos 98% citados no texto da página. |
| OK no prazo | 45% | Definição exata do SLA não informada. |
| TMR geral | 4,12 | Unidade e definição não informadas. |
| RMS | 4,22 | Definição não informada. |
| Aberturas via 0800 | 19% | Dado apresentado no texto corrido. |
| Tickets de Orientação de uso | 13% | Dado apresentado no texto corrido. |
| Agentes N1 mobilizados | 10, em média | Usados para abertura de tickets via telefone. |

## 4. Objetivos declarados

O quadro executivo lista três objetivos centrais:

1. aumentar a quantidade de tickets “OK no prazo”, sob a perspectiva do cliente;
2. otimizar o uso de especialistas N1 e das visitas técnicas;
3. introduzir checks prévios no atendimento de Manutenção e em jornadas relacionadas, como DMA.

Traduzidos para resultados de negócio, esses objetivos significam:

- maior contenção no autosserviço;
- menos ligações usadas apenas para abertura de chamado;
- menor número de deslocamentos improdutivos;
- melhor diagnóstico na origem;
- fechamento remoto quando o cliente confirma a solução;
- priorização mais inteligente dos casos que realmente precisam de atendimento humano ou visita.

## 5. Solução proposta

### 5.1 Modelo de atendimento em camadas

A proposta organiza o atendimento em três níveis:

1. **Chatbot / autosserviço:** coleta dados e conduz checks simples.
2. **Telemanutenção com N1 especializado:** realiza checagem remota, potencialmente por vídeo.
3. **Visita física:** usada somente quando o problema não foi resolvido remotamente.

### 5.2 Macrofluxo da Telemanutenção

O diagrama da página representa a seguinte jornada:

```text
Contato pelo 0800 ou WhatsApp
  → validação DMA
  → confirmação das informações cadastrais
      - contato
      - endereço
      - descrição/prévia do problema
  → checks técnicos
      - temperatura
      - conexões de energia
      - display
  → cliente confirma que o problema foi resolvido?
      ├─ sim → encerramento do atendimento
      └─ não → Telemanutenção por agente especializado/vídeo
                  → problema solucionado?
                      ├─ sim → encerramento do atendimento
                      └─ não → visita física
```

### 5.3 Checks prévios inspirados na Claro

A página usa como referência visual uma jornada da Claro chamada “Antes de abrir um chamado”. Ela orienta o cliente a:

- reiniciar o modem;
- verificar se outros equipamentos conseguem se conectar à internet;
- verificar se os cabos estão conectados corretamente;
- desconectar um equipamento da tomada.

O aprendizado transferido para Manutenção é o desenho de verificações simples, guiadas e executáveis pelo cliente antes da abertura ou do encaminhamento do chamado. Os checks específicos de equipamentos devem respeitar regras de segurança próprias do domínio.

## 6. Evoluções de processo e tecnologia

O quadro executivo distribui as mudanças em blocos de capacidade.

### 6.1 Autosserviço

- FAQ ilustrada de Manutenção;
- integração de DMA ao aplicativo;
- revisão do fluxo de abertura no chatbot e no 0800 para incluir Telemanutenção.

### 6.2 Fluxo operacional

- fechamento do ticket com código de validação;
- abertura com validação de técnico e contato;
- identificação/validação de chamados improdutivos;
- prioridade de atendimento;
- melhoria da visibilidade para a camada N1.

### 6.3 Chatbot e automações

O quadro associa ao chatbot:

- Telemanutenção;
- validação de código de verificação;
- revisão do fluxo/plano dentro do chat;
- participação dos especialistas envolvidos.

Também é citada uma automação para validar a resolubilidade da oferta.

### 6.4 IA e insights digitais

O material aponta duas aplicações de agente generativo:

- triagem dos tickets na entrada por **áudio e texto**;
- triagem a partir do problema de Manutenção, relacionada à atuação da Embrasac.

Também é mencionada uma frente preventiva para equipamentos de chope e PostMix, apresentada como “modelo squad encantamento”. Essa frente aparece no quadro, mas não é detalhada no texto principal.

## 7. Parceiros e estratégia de validação

### Twilio

- testes de vídeo já iniciados;
- validação do recebimento de vídeo marcada como concluída no checklist;
- objetivo provável: habilitar inspeção remota visual durante a Telemanutenção.

> O texto do Loop escreve “Twillio”; neste documento foi usada a grafia oficial “Twilio”.

### Embrasac

- empresa apresentada como especializada em atendimento remoto de manutenção;
- discussões ainda em fase embrionária;
- possível participação em provas de conceito e teste A/B.

### Estratégia experimental

- POCs antes da expansão;
- teste A/B para comparar abordagens;
- primeiros testes com base validada;
- rollout faseado por GEO após definição do melhor caminho.

## 8. Cronograma informado

O Loop afirma que os testes iniciais com a base validada e os primeiros resultados começariam em **junho**. O ano não é informado na página, portanto essa data não deve ser tratada como compromisso vigente sem confirmação.

Depois da validação inicial, o rollout seria feito gradualmente por GEO.

## 9. Status dos próximos passos

### Concluídos na página

- [x] Testes e validação com a Twilio.
- [x] Testes do recebimento do vídeo.

### Pendentes na página

- [ ] Redefinição da jornada de Manutenção no chatbot.
- [ ] Contratação da equipe responsável pelo fluxo.
- [ ] Definição da base foco, inicialmente composta por clientes recorrentes em “Orientação de uso”.

## 10. Hipóteses que o piloto precisa validar

Com base no conteúdo do Loop, o piloto depende das seguintes hipóteses:

1. clientes conseguem executar checks básicos com instruções remotas;
2. migrar abertura do 0800 para o chatbot reduz esforço de N1 sem aumentar abandono;
3. vídeo adiciona informação suficiente para melhorar o diagnóstico remoto;
4. um N1 especializado resolve parte relevante dos casos antes da visita;
5. clientes recorrentes de “Orientação de uso” são uma boa base inicial;
6. a confirmação do cliente é confiável para encerrar o chamado;
7. a solução é escalável entre GEOs sem grande variação de processo.

## 11. Métricas recomendadas para o piloto

O Loop não apresenta uma árvore formal de métricas. Para medir as hipóteses descritas, o piloto deveria acompanhar:

| Dimensão | Métrica |
|---|---|
| Adoção | Percentual dos contatos elegíveis que iniciam e concluem a jornada digital. |
| Contenção | Percentual resolvido pelo chatbot sem intervenção humana. |
| Resolução remota | Percentual resolvido após atuação do N1/Telemanutenção. |
| Visita evitada | Casos elegíveis resolvidos remotamente e confirmados pelo cliente. |
| Conversão de canal | Redução de aberturas de Manutenção via 0800. |
| Eficiência operacional | Horas/FTE de N1 economizadas na abertura e triagem. |
| Qualidade | Reabertura ou reincidência após fechamento remoto. |
| SLA | Evolução do percentual “OK no prazo”. |
| Experiência | Satisfação do cliente após a jornada remota. |
| Segurança | Casos interrompidos/encaminhados por risco e incidentes causados por orientação. |
| Vídeo | Taxa de conexão, qualidade, abandono e ganho de resolução atribuído ao vídeo. |
| Financeiro | Custo por atendimento remoto, custo por visita evitada e economia líquida. |

## 12. Dependências, riscos e pontos em aberto

### Dependências

- integração entre chatbot, DMA, sistema de tickets e canais de contato;
- disponibilidade de agentes N1 com especialização em Manutenção;
- infraestrutura e consentimento para atendimento por vídeo;
- regras claras de encerramento, validação e priorização;
- base elegível e histórico confiável de tickets;
- operação de campo preparada para receber casos enriquecidos pela triagem.

### Riscos

- orientar remotamente ações inseguras no equipamento;
- fechar ticket sem confirmação confiável de resolução;
- deslocar o volume do telefone para uma jornada digital com baixa conclusão;
- criar uma etapa de vídeo cara sem ganho proporcional de resolução;
- subestimar diferenças regionais no rollout por GEO;
- medir automação em vez de resolução efetiva e recorrência;
- duplicar registros entre chatbot, 0800 e sistema de tickets.

### Pontos que a fonte não esclarece

- significado oficial das siglas DMA, TMR e RMS;
- período e fórmula do custo de FTEs;
- motivo da divergência entre 94% e 98% de automação;
- definição exata de “OK no prazo”;
- ano do início dos testes em junho;
- critérios de elegibilidade e exclusão do piloto;
- quais checks são permitidos para cada tipo de equipamento;
- regra de timeout ou ausência de resposta do cliente;
- dados coletados no vídeo, retenção, consentimento e privacidade;
- integração responsável pelo fechamento do ticket e pelo código de validação;
- desenho e tamanho dos grupos do teste A/B.

## 13. Relação com o CoolCare MVP

Esta seção é uma análise aplicada ao projeto local e **não faz parte do conteúdo original do Loop**.

O estudo de Telemanutenção reforça diretamente o desenho do CoolCare:

| Telemanutenção do Loop | CoolCare MVP |
|---|---|
| Checks simples antes de despachar visita | Checklist remoto seguro para coolers e geladeiras. |
| Escalonamento para N1 especializado | Encaminhamento ao fornecedor quando o agente não resolve. |
| Atendimento remoto com evidência visual | Upload e leitura da foto da etiqueta; possibilidade futura de vídeo. |
| Confirmação do cliente antes do encerramento | Status `resolvido_remotamente` somente após confirmação positiva do PDV. |
| Casos não resolvidos seguem para visita | Status `encaminhado_fornecedor` com contexto e evidências. |
| Foco em “Orientação de uso” | Sintomas com verificações externas, simples e seguras. |
| Redução de chamadas e visitas improdutivas | Métrica de visita evitada e economia associada. |
| IA para triagem de texto/áudio | Agente CrewAI interpreta a conversa e devolve dados estruturados. |

### Diferenças relevantes

- O Loop prevê operação real com chatbot, 0800, DMA, N1, vídeo e rollout geográfico; o CoolCare atual é um MVP demonstrativo sem integrações reais.
- O Loop não detalha guardrails de segurança; o CoolCare proíbe abertura do equipamento, reparo elétrico e manipulação interna.
- O Loop sugere fechamento com código de validação; o CoolCare usa confirmação explícita do PDV e encaminhamento automático após 30 minutos sem resposta.
- O Loop apresenta PostMix e chope como frente adicional; o CoolCare restringe o MVP a coolers e geladeiras.

## 14. Recomendações aproveitáveis para o novo projeto

1. **Separar automação de resolução:** automação de abertura não deve ser a métrica principal; medir resolução confirmada, reincidência e visita evitada.
2. **Começar por uma coorte de alto potencial:** clientes recorrentes em “Orientação de uso” são um bom modelo de seleção inicial.
3. **Enriquecer o encaminhamento:** enviar ao fornecedor identificação do equipamento, sintoma, evidências e checks já executados.
4. **Manter decisão híbrida:** IA conduz a conversa; regras determinísticas controlam segurança, timeout e escalonamento.
5. **Tratar vídeo como experimento:** medir ganho incremental antes de incorporar custo e complexidade ao fluxo padrão.
6. **Validar por teste A/B:** comparar jornada atual e jornada remota usando resolução, reabertura, tempo e satisfação.
7. **Planejar rollout por segmento/GEO:** validar variações operacionais antes da expansão.
8. **Definir taxonomia e glossário:** documentar siglas, motivos de contato, códigos de fechamento e critérios de “visita evitada”.
9. **Construir guardrails explícitos:** interromper a orientação e escalar imediatamente diante de risco elétrico, vazamento, faísca, cheiro de queimado ou dano físico.
10. **Exigir confirmação para contabilizar benefício:** somente considerar visita evitada quando a resolução for confirmada e não houver reincidência na janela acordada.

## 15. Qualidade e limitações desta extração

- O texto corrido, checklists e macrofluxo foram lidos diretamente na página do Loop.
- Parte dos indicadores e das capacidades foi transcrita de imagens incorporadas; siglas e rótulos de baixa legibilidade foram preservados de forma conservadora.
- Não foram inventadas expansões para siglas sem definição na fonte.
- Recomendações, hipóteses e a comparação com o CoolCare estão identificadas como análise, separadas do conteúdo factual do Loop.
- A página é dinâmica; status, números e cronograma podem ter sido alterados após a data de extração.
