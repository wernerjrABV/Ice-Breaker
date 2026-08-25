# Ice Breakers — respostas para os templates do Hackathon

> **Nota:** este documento usa somente as informações fornecidas na ideia aprovada, no texto original e nos valores revisados. Todo item sem informação confirmada está em <span style="color:red">vermelho</span>.

## Identificação

- **Time:** TEAM 8 — Ice Breakers
- **Zona / País:** SAZ / BR
- **BU / Área:** Draftline / Data
- **Integrantes:** Daniel Gonçalves (Architect), Diego Zaratine (Architect), Larissa Marchi (Eng Manager), Marcos de Souza (Product Owner) e Werner Junior (Eng Manager).
- **BU Owner:** <span style="color:red">Não informado.</span>
- **Tech Owner:** <span style="color:red">Não informado.</span>

---

## Template 1 — Project overview

### 1. Project in one sentence

> Estamos construindo um agente de IA generativa para manutenção de coolers, destinado ao suporte de primeiro nível e aos pontos de venda, para resolver remotamente casos elegíveis, reduzir acionamentos técnicos desnecessários e melhorar a rastreabilidade dos ativos.

### 2. Problem or opportunity

- **Problema atual:** solicitações de manutenção de coolers podem seguir para fornecedor ou técnico de campo sem uma triagem inicial suficientemente estruturada e padronizada. Casos resolvíveis com orientação, checklist simples ou suporte remoto podem consumir recursos de campo.
- **Quem é afetado:** equipes de operações de coolers, manutenção e gestão de ativos; fornecedores e técnicos de campo; clientes e pontos de venda que dependem dos equipamentos; e a empresa, pelos custos operacionais e pela visibilidade limitada dos ativos.
- **Processo atual:** abertura de solicitação de manutenção seguida do acionamento de fornecedor ou técnico de campo. A qualidade do diagnóstico depende das informações registradas na abertura; dados incompletos, pouco detalhados ou sem identificação correta do equipamento dificultam o diagnóstico.
- **Por que importa:** visitas evitáveis geram custo operacional, reduzem a produtividade do campo e podem aumentar o tempo de resolução. A rastreabilidade incompleta do cooler, número de série e histórico de manutenção também dificulta diagnóstico, auditoria, priorização e gestão da base instalada.
- **Evidência / baseline disponível:** análise dos últimos três meses, com **67.448 tickets** de manutenção. Desses, **14.324** têm potencial de resolução remota (orientação, instrução de uso ou suporte de call center); **30.141** apresentam forte indicação de necessidade real de intervenção técnica, como troca de peça ou substituição técnica.

### 3. Proposed solution

- **Visão geral:** agente especializado de IA generativa como primeiro nível de suporte à manutenção de coolers, antes do acionamento de fornecedores ou técnicos de campo.
- **Como funciona:** o agente recebe a descrição do problema e, quando disponível, foto, etiqueta ou número de série. Ele consulta a base histórica de tickets, manuais técnicos e fluxos de diagnóstico para orientar uma triagem e recomendar resolução remota ou escalonamento técnico.
- **Ações dos usuários:** o suporte ou ponto de venda segue um checklist guiado de procedimentos simples e seguros, por exemplo limpeza, verificação básica de energia, degelo, validação de alimentação elétrica e uso correto do equipamento.
- **Ações da GenAI:** classificar a solicitação, identificar padrões de falha e possíveis causas, sugerir orientações e decidir, com base nas evidências disponíveis, se o caso deve ser resolvido remotamente ou encaminhado para visita técnica. O agente não substitui o técnico.
- **Visão computacional:** a solução pode ler uma foto da etiqueta ou do número de série para identificar o equipamento instalado no cliente, conectar o chamado ao histórico correto e melhorar a rastreabilidade dos ativos.
- **O que pode ser demonstrado:** um MVP como assistente para suporte ou pontos de venda selecionados, usando tickets históricos, manuais e regras de triagem para produzir checklist guiado e recomendação “resolver remotamente” ou “acionar técnico”.

### 4. GenAI & technology approach

- **Caso de uso GenAI:** suporte de primeiro nível e triagem inteligente de manutenção de coolers.
- **Fontes de conhecimento:** banco histórico de tickets de manutenção, manuais técnicos dos equipamentos e fluxo guiado de diagnóstico/regras operacionais.
- **Uso de IA:** interpretação da descrição do caso, classificação, recomendação de ações simples e seguras, sugestão de possível causa e preparação de um encaminhamento mais completo para o fornecedor quando necessário.
- **Visão computacional:** leitura de etiqueta ou número de série a partir de imagem, quando disponível.
- **Evolução prevista:** integração futura com sistemas de tickets e aprendizado a partir dos desfechos reais dos atendimentos encerrados.
- **Modelo de IA, assistente, orquestração, plataforma de automação e arquitetura detalhada:** <span style="color:red">Não informados.</span>

---

## Template 2 — Judges pre-read

### Project objective (one tweet — até 280 caracteres)

> Agente GenAI para triagem de manutenção de coolers que usa tickets, manuais e diagnóstico guiado para resolver casos elegíveis remotamente, reduzir visitas técnicas evitáveis, melhorar a qualidade dos chamados e aumentar a rastreabilidade dos ativos.

### Business challenge

> Reduzir acionamentos desnecessários de técnicos para manutenção de coolers e melhorar a qualidade da triagem, do diagnóstico e da rastreabilidade dos equipamentos no campo.

### Current baseline

- **Fluxo atual:** abertura de chamado de manutenção e acionamento de fornecedor/técnico; a triagem inicial não parece totalmente padronizada, automatizada ou apoiada por uma base de conhecimento inteligente.
- **Principais dores:** informações incompletas ou sem identificação correta do equipamento reduzem a precisão do diagnóstico; ocorrências simples podem seguir o mesmo fluxo de atendimento técnico de casos complexos; rastreabilidade depende de dados cadastrais e registros manuais.
- **Evidência disponível:** 67.448 tickets analisados em três meses; 14.324 tickets com potencial de resolução remota; 30.141 com forte indicação de intervenção técnica real.
- **Ferramentas existentes:** <span style="color:red">Não informadas.</span>

### Expected benefits

- **Tipo de benefício:** economia de OPEX / redução de custo operacional, pela redução de visitas técnicas evitáveis.
- **Base de cálculo:** custo médio por atendimento de **R$ 200**; câmbio utilizado de **R$ 5,50/US$**; potencial de 14.324 tickets de resolução remota em três meses.
- **Potencial anual bruto estimado (100%):** **R$ 11.459.200**, ou **US$ 2.083.491**.
- **Cenário de captura de 50%:** **R$ 5.729.600/ano**, ou aproximadamente **US$ 1,04 milhão/ano**.
- **Cenário de captura de 60%:** **R$ 6.875.520/ano**, ou aproximadamente **US$ 1,25 milhão/ano**.
- **Cenário de 75%:** **R$ 8.594.400/ano**, ou aproximadamente **US$ 1,56 milhão/ano**. <span style="color:red">Este cenário foi calculado a partir dos valores revisados, mas não é um dos dois percentuais que devem substituir os percentuais enviados originalmente.</span>
- **Custo de implementação e ROI/payback numérico:** <span style="color:red">Não informados. A proposta apenas descreve o custo como moderado em relação ao potencial de economia e prevê investimentos em preparação de dados, manuais, agente/RAG, fluxos, integrações, reconhecimento por imagem e treinamento.</span>

### Proposed solution (one tweet)

> Um agente GenAI consulta tickets históricos, manuais e fluxos de diagnóstico para orientar suporte e pontos de venda, classificar chamados, recomendar resolução remota segura ou escalonamento técnico e, quando houver imagem, identificar o cooler por etiqueta ou número de série.

**Fluxo resumido:**

`Descrição do problema / foto / número de série → Agente GenAI → Consulta a tickets, manuais e regras → Checklist e recomendação → Resolução remota ou acionamento técnico → Menos visitas evitáveis e melhor rastreabilidade`

### Data

- **Datasets:** histórico de tickets de manutenção; manuais técnicos dos equipamentos; fluxos/regras de diagnóstico.
- **Sistemas de origem, APIs e integração de ticketing:** <span style="color:red">Não informados.</span>
- **Segurança e controles de acesso:** <span style="color:red">Não informados.</span>

### Scale potential

- **Usuários potenciais iniciais:** equipe de suporte e pontos de venda selecionados.
- **Expansão prevista:** integrar ao sistema de tickets, automatizar a leitura de etiquetas/números de série e incorporar o resultado real dos atendimentos para melhorar as recomendações.
- **Outros times / países / BUs alvo:** <span style="color:red">Não informados.</span>

### Technology stack

- **Capacidades previstas:** GenAI com RAG sobre tickets e manuais; regras/fluxos de diagnóstico; visão computacional para etiqueta ou número de série; futura integração ao ticketing.
- **Tecnologias, fornecedores, linguagens, plataformas e APIs específicas:** <span style="color:red">Não informados.</span>

---

## Template 3 — Benefit validation

| # | Componente de benefício | Categoria | Linha de P&L | Baseline | Incremental anual | Evidência | Já capturado? |
|---|---|---|---|---:|---:|---|---|
| 1 | Redução de custos por evitar visitas técnicas elegíveis para resolução remota — cenário de 50% | Cost Reduction | OPEX | <span style="color:red">Não informado.</span> | R$ 5.729.600 (≈ US$ 1,04 mi) | B — análise histórica de tickets (3 meses), custo médio de R$ 200 e câmbio de R$ 5,50/US$ | <span style="color:red">Não informado.</span> |
| 2 | Redução de custos por evitar visitas técnicas elegíveis para resolução remota — cenário de 60% | Cost Reduction | OPEX | <span style="color:red">Não informado.</span> | R$ 6.875.520 (≈ US$ 1,25 mi) | B — análise histórica de tickets (3 meses), custo médio de R$ 200 e câmbio de R$ 5,50/US$ | <span style="color:red">Não informado.</span> |

> **Importante:** os cenários de 50% e 60% são alternativas de captura do mesmo potencial; não devem ser somados entre si como benefícios independentes.

### Cálculo revisado

1. Tickets com potencial de resolução remota em três meses: **14.324**.
2. Economia mensal potencial: `(14.324 × R$ 200) ÷ 3 = R$ 954.933`.
3. Economia anual potencial: `R$ 954.933 × 12 = R$ 11.459.200`.
4. Conversão utilizada: `R$ 11.459.200 ÷ 5,50 = US$ 2.083.491`.
5. Captura de 50%: aproximadamente **US$ 1,04 milhão/ano**.
6. Captura de 60%: aproximadamente **US$ 1,25 milhão/ano**.

### Informações ainda necessárias para validação completa

- <span style="color:red">BU Owner e Tech Owner.</span>
- <span style="color:red">Nome dos sistemas de tickets, fontes de dados, APIs e requisitos de segurança.</span>
- <span style="color:red">Custo estimado de implementação, prazo, ROI e payback calculados.</span>
- <span style="color:red">Linha de P&L específica e confirmação de que a economia ainda não está capturada por outra iniciativa.</span>
- <span style="color:red">Confirmação formal da evidência e do critério usado para classificar os 14.324 tickets como elegíveis à resolução remota.</span>

