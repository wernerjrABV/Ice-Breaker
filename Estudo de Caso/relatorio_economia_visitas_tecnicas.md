# Relatório de Economia Potencial com Visitas Técnicas — Versão Atualizada

## Objetivo

Estimar uma economia realista com redução de visitas técnicas, considerando custo médio de **R$ 200 por visita** e o novo campo `TicketStatusDetail`, que registra o resultado ou motivo do atendimento.

Foram analisados **67.448 tickets**.

## O que os novos dados permitem concluir

O campo `TicketStatusDetail` fornece evidência mais próxima do desfecho real:

- **28.039** tickets terminaram com `REPAIRED_WITH_PARTS_REPLACEMENT`;
- **2.102** terminaram com `TECHNICAL_EXCHANGE`;
- **11.957** terminaram com `REPAIRED_WITH_GUIDANCE`;
- **2.090** registraram instrução de uso;
- **277** registraram orientação de call center;
- **12.234** não possuem detalhe informado.

## Premissas conservadoras

Para não superestimar o saving:

- nenhum ticket com troca de peça ou troca técnica foi considerado visita evitável;
- apenas **50% dos tickets `REPAIRED_WITH_GUIDANCE`** foram considerados potencialmente evitáveis;
- 100% dos tickets com instrução de uso ou `CALL_CENTER_GUIDANCE` foram considerados candidatos a evitar visita, desde que o procedimento seja incorporado ao PDV ou ao atendimento remoto;
- chamados administrativos, logísticos e de ausência não foram convertidos automaticamente em saving, pois podem já ter sido encerrados sem visita;
- não foram descontados custos de equipe remota, treinamento, ferramentas, peças, retrabalho ou segunda visita.

## Fórmula utilizada

```text
Visitas evitadas estimadas =
    50% × REPAIRED_WITH_GUIDANCE
    + instruções de uso
    + CALL_CENTER_GUIDANCE
```

```text
Economia bruta = visitas evitadas estimadas × R$ 200
```

## Estimativa conservadora por mês

| Mês | `REPAIRED_WITH_GUIDANCE` | Instruções/call center | Visitas evitadas | Economia bruta |
|---|---:|---:|---:|---:|
| Abril/2026 | 1.016 | 36 | 544 | **R$ 108.800** |
| Maio/2026 | 4.189 | 622 | 2.716 | **R$ 543.200** |
| Junho/2026 | 3.772 | 938 | 2.824 | **R$ 564.800** |
| Julho/2026 | 2.980 | 771 | 2.261 | **R$ 452.200** |
| **Total** | **11.957** | **2.367** | **8.345** | **R$ 1.669.000** |
| **Média mensal** | — | — | **2.086** | **R$ 417.250** |

## Faixa de planejamento

O número mais defensável com os dados atuais é uma economia bruta média de aproximadamente **R$ 417 mil por mês**.

Para planejamento, recomenda-se considerar uma faixa de **R$ 300 mil a R$ 500 mil por mês**, até que seja confirmado quantos tickets `REPAIRED_WITH_GUIDANCE` realmente evitaram uma visita técnica.

O valor de R$ 500 mil não deve ser tratado como garantia; ele representa um cenário de execução eficiente do roteiro de orientação e boa adesão do PDV.

## Cenário ainda mais prudente

Se apenas 30% dos tickets `REPAIRED_WITH_GUIDANCE` forem efetivamente evitáveis, mantendo 100% das instruções e orientações de call center, a economia seria:

| Indicador | Estimativa |
|---|---:|
| Visitas evitadas no período | 5.953 |
| Economia total em quatro meses | **R$ 1.190.600** |
| Economia média mensal | **R$ 297.650** |

## Cenários de 60% e 75%

Além do cenário prudente de 30% e do cenário-base de 50%, foram calculados dois cenários adicionais. Neles, considera-se que 60% ou 75% dos tickets `REPAIRED_WITH_GUIDANCE` poderiam ser resolvidos sem visita, mantendo 100% das instruções de uso e dos atendimentos `CALL_CENTER_GUIDANCE` como candidatos a evitar deslocamento.

### Cenário de 60%

| Mês | Visitas evitadas | Economia bruta |
|---|---:|---:|
| Abril/2026 | 646 | **R$ 129.200** |
| Maio/2026 | 3.135 | **R$ 627.000** |
| Junho/2026 | 3.201 | **R$ 640.200** |
| Julho/2026 | 2.559 | **R$ 511.800** |
| **Total** | **9.541** | **R$ 1.908.200** |
| **Média mensal** | **2.385** | **R$ 477.050** |

### Cenário de 75%

| Mês | Visitas evitadas | Economia bruta |
|---|---:|---:|
| Abril/2026 | 798 | **R$ 159.600** |
| Maio/2026 | 3.764 | **R$ 752.800** |
| Junho/2026 | 3.767 | **R$ 753.400** |
| Julho/2026 | 3.006 | **R$ 601.200** |
| **Total** | **11.335** | **R$ 2.267.000** |
| **Média mensal** | **2.834** | **R$ 566.750** |

### Comparativo dos cenários

| Percentual de `REPAIRED_WITH_GUIDANCE` evitável | Visitas evitadas no período | Economia média mensal |
|---:|---:|---:|
| 30% | 5.953 | **R$ 297.650** |
| 50% | 8.345 | **R$ 417.250** |
| 60% | 9.541 | **R$ 477.050** |
| 75% | 11.335 | **R$ 566.750** |

O cenário de 75% deve ser tratado como uma meta de eficiência, e não como previsão inicial. Para apresentação gerencial, o cenário de 50% continua sendo a referência conservadora principal, enquanto 60% e 75% representam níveis de maturidade operacional após a implantação dos checklists e do atendimento remoto.

Esse cenário é apropriado para uma meta inicial de implantação, pois considera que parte das orientações pode ter ocorrido depois de uma visita ou em situações que ainda exigem acompanhamento técnico.

## O que não deve ser contado como saving automaticamente

Os seguintes registros não devem ser considerados economia sem saber se uma visita havia sido agendada:

- cliente ausente ou não autorizado;
- endereço errado ou inválido;
- equipamento não localizado;
- solicitação de contratante;
- duplicidade;
- regularização de abertura de contrato;
- equipamento não suportado;
- produto removido ou área não atendida.

Eles podem reduzir custos operacionais, mas não necessariamente representam visitas evitadas.

## Risco de subestimação

Os **12.234 tickets sem `TicketStatusDetail`** podem conter casos resolvidos por orientação ou instrução. Se parte deles for corretamente detalhada, o potencial de saving poderá aumentar. No entanto, não é adequado incluir esse volume na projeção antes de realizar uma amostragem.

## Recomendação executiva

> Com base nos resultados registrados no novo campo, uma estimativa conservadora aponta para aproximadamente **2.086 visitas evitadas por mês**, equivalentes a **R$ 417 mil de economia bruta mensal**. Para uma meta inicial segura, recomenda-se trabalhar com **R$ 300 mil mensais** e revisar o número após medir quantas orientações realmente evitam o deslocamento técnico.

## Indicadores que devem ser acompanhados

1. Percentual de `REPAIRED_WITH_GUIDANCE` sem visita técnica.
2. Percentual de instruções de uso resolvidas pelo PDV.
3. Taxa de reabertura após orientação.
4. Taxa de segunda visita.
5. Custo médio real por visita, incluindo deslocamento e peças.
6. Percentual de tickets sem `TicketStatusDetail`.

## Conclusão

O novo campo reduz a dependência de inferências feitas apenas pela descrição. Ele mostra que a oportunidade de saving mais segura está nos tickets já encerrados com orientação, instruções de uso e atendimento de call center. Com premissas conservadoras, o saving estimado é de **R$ 297 mil a R$ 417 mil por mês**, sendo **R$ 300 mil mensais** uma meta inicial mais realista até que a operação confirme a quantidade efetiva de visitas evitadas.
