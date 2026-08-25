# Relatório de Direcionamento dos Atendimentos — Versão Atualizada

## Objetivo

Avaliar quais tickets podem ser resolvidos pelo próprio PDV, tratados remotamente ou encaminhados para técnico, agora considerando também o resultado registrado em `TicketStatusDetail`.

Foram analisados **67.448 tickets**, combinando `Description`, `Descriptions` e `TicketStatusDetail`.

## Evidência dos resultados registrados

| `TicketStatusDetail` | Tickets | Percentual | Interpretação operacional |
|---|---:|---:|---|
| `REPAIRED_WITH_PARTS_REPLACEMENT` | 28.039 | 41,57% | Forte indicação de intervenção técnica e/ou troca de peça |
| `REPAIRED_WITH_GUIDANCE` | 11.957 | 17,73% | Caso resolvido com orientação; potencial de prevenção de visita |
| `TECHNICAL_EXCHANGE` | 2.102 | 3,12% | Forte indicação de atendimento técnico presencial |
| Instruções de uso | 2.090 | 3,10% | Candidato a resolução pelo PDV ou atendimento remoto |
| `CALL_CENTER_GUIDANCE` | 277 | 0,41% | Evidência de tratamento remoto |
| `SOLICITED_BY_CONTRACTOR` | 4.988 | 7,40% | Solicitação operacional/contratual; não necessariamente defeito |
| Impedimentos logísticos | 3.576 | 5,30% | Ausência, endereço incorreto ou equipamento não localizado |
| Outros administrativos | 2.419 | 3,59% | Regularização, duplicidade, autorização e situações administrativas |
| Não informado | 12.234 | 18,14% | Sem evidência suficiente para classificar o desfecho |

## Direcionamento recomendado

### Técnico no local

Devem ser tratados como alta probabilidade de técnico:

- `REPAIRED_WITH_PARTS_REPLACEMENT`: **28.039 tickets**;
- `TECHNICAL_EXCHANGE`: **2.102 tickets**.

Esses registros somam **30.141 tickets — 44,69%**. A evidência indica que são ocorrências com maior probabilidade de exigir inspeção física, reparo ou substituição de componentes.

### Atendimento remoto ou resolução pelo PDV

Há evidência de que pelo menos **14.324 tickets — 21,23%** foram tratados sem troca de peça registrada, por orientação, instrução de uso ou atendimento de call center:

- `REPAIRED_WITH_GUIDANCE`: **11.957**;
- instruções de uso: **2.090**;
- `CALL_CENTER_GUIDANCE`: **277**.

Esse grupo deve ser dividido operacionalmente:

- instruções elétricas, limpeza de condensador, limpeza de gelo e alimentação: roteiro para o PDV, desde que não envolva abertura ou risco elétrico;
- orientação de reparo: atendimento remoto com diagnóstico guiado;
- casos não resolvidos após o roteiro: escalonamento para técnico.

### Chamados que não devem gerar visita automaticamente

Os seguintes grupos devem passar por validação administrativa ou logística antes de qualquer agendamento:

- `SOLICITED_BY_CONTRACTOR`: 4.988;
- cliente ausente ou não autorizado: 3.576;
- equipamento não localizado, endereço inválido e área não atendida;
- duplicidades, regularizações e chamados sem problema técnico claro.

Esses registros não devem ser contabilizados como defeitos técnicos sem confirmação.

## Limitação mais importante

Existem **12.234 tickets sem `TicketStatusDetail`**. Além disso, `REPAIRED_WITH_GUIDANCE` não informa sozinho se a orientação ocorreu antes de uma visita ou se evitou uma visita. Por isso, esse grupo não deve ser convertido integralmente em saving sem validação operacional.

## Fluxo recomendado

```text
Ticket aberto
    ↓
Verificar TicketStatusDetail e identificar chamado administrativo
    ├── Administrativo/logístico → tratar sem agendar visita automaticamente
    └── Técnico provável / troca de peça → priorizar técnico
         ↓
    PDV ou atendimento remoto
         ├── Resolvido → encerrar
         └── Não resolvido → agendar técnico
```

## Recomendações

1. Usar `TicketStatusDetail` como campo de controle do resultado do atendimento.
2. Criar checklists para os tickets com orientação e instrução de uso.
3. Separar troca de peça e troca técnica dos casos resolvidos por orientação.
4. Bloquear agendamento automático em chamados administrativos ou logísticos.
5. Tornar `TicketStatusDetail` obrigatório no encerramento do ticket.
6. Auditar uma amostra dos 12.234 tickets sem detalhe.

## Conclusão

Os novos dados tornam a análise mais confiável. Eles mostram uma base de **14.324 tickets com evidência de orientação ou instrução** e **30.141 tickets com forte indicação de intervenção técnica**. A principal oportunidade está em transformar os atendimentos com orientação em um processo padronizado de PDV e suporte remoto, sem assumir que todos eles representam visitas evitáveis.
