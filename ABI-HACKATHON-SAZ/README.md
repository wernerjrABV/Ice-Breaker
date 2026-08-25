# CoolCare — Hackathon SAZ Grand Slam

O CoolCare é um MVP de triagem segura para chamados de coolers e geladeiras. O front-end React conversa com o back-end FastAPI, que persiste o atendimento em SQLite e consulta a API do agente CrewAI quando necessário.

```text
Front-end :5173 → Back-end :8001 → Agente :8000
```

## Pré-requisitos

- Python compatível com cada `pyproject.toml` (o agente aceita 3.10 até 3.13; o back-end requer 3.13 ou superior)
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 ou superior e npm (validado com Node.js 24.18.0)

Os comandos abaixo são para Windows PowerShell e partem da pasta `ABI-HACKATHON-SAZ`.

## Configuração inicial

Crie os três arquivos locais de ambiente:

```powershell
Copy-Item agent/.env.example agent/.env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

Edite `agent/.env` e substitua o valor de exemplo de `OPENAI_API_KEY`. `OPENAI_MODEL` configura tanto a leitura de etiqueta quanto a intenção estruturada da conversa; quando a variável está ausente ou vazia, os dois adaptadores usam `openai/gpt-4o-mini`, compatível com o CrewAI 1.3.0 fixado no projeto. O arquivo de exemplo explicita esse mesmo padrão. Os exemplos do back-end e do front-end já apontam para as portas locais padrão. Nunca versione os arquivos `.env` nem cole a chave em comandos, logs ou capturas de tela.

## Iniciar os serviços

Abra três terminais PowerShell.

Terminal 1 — agente em `http://127.0.0.1:8000`:

```powershell
Set-Location agent
uv sync
uv run api
```

Terminal 2 — back-end em `http://127.0.0.1:8001`:

```powershell
Set-Location backend
uv sync
$env:DEMO_MODE = "true"
uv run api
```

`DEMO_MODE=true` permite somente que o roteiro passe um relógio acelerado à rota de expiração. Esse relógio fornecido pelo cliente considera exclusivamente os quatro IDs fixos da demo e nunca expira outros chamados. Para execução normal, omita essa variável ou use `$env:DEMO_MODE = "false"`; sem o parâmetro `now`, a manutenção continua examinando todos os chamados legitimamente vencidos pelo relógio real, e o timeout permanece em 30 minutos.

Terminal 3 — front-end em `http://localhost:5173`:

```powershell
Set-Location frontend
npm install
npm run dev
```

Inicie os serviços na ordem agente, back-end e front-end. A documentação interativa do back-end fica em `http://127.0.0.1:8001/docs`.

## Dashboard do agente

Com um chamado aberto, o painel à direita acompanha `GET /tickets/{id}/events` a cada segundo. Atualizar a página reconstrói o histórico do chamado a partir desses eventos. O cartão de **R$ 200** representa economia potencial até a confirmação positiva do PDV; somente então passa a ser economia realizada.

## Roteiro de demonstração repetível

Em um quarto terminal, defina a URL e restaure os quatro chamados. A restauração recria somente os IDs `DEMO-*`; chamados reais ou criados manualmente são preservados.

```powershell
$api = "http://127.0.0.1:8001"
$demoIds = Invoke-RestMethod -Method Post -Uri "$api/demo/reset"
$demoIds
```

O resultado é sempre:

```text
DEMO-REMOTE
DEMO-DOOR
DEMO-SUPPLIER
DEMO-URGENT
```

### 1. Resolução remota — Congela bebidas

Abra o chamado e avance pela proximidade, identificação e confirmação positiva:

```powershell
Invoke-RestMethod -Method Get -Uri "$api/tickets/DEMO-REMOTE"
Invoke-RestMethod -Method Post -Uri "$api/tickets/DEMO-REMOTE/messages" -ContentType "application/json" -Body (@{ content = "sim" } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$api/tickets/DEMO-REMOTE/equipment/serial" -ContentType "application/json" -Body (@{ modelo = "CX-400"; numero_serie = "BR-DEMO-001" } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$api/tickets/DEMO-REMOTE/messages" -ContentType "application/json" -Body (@{ content = "sim, os dados estão corretos" } | ConvertTo-Json)
$remote = Invoke-RestMethod -Method Post -Uri "$api/tickets/DEMO-REMOTE/messages" -ContentType "application/json" -Body (@{ content = "sim, resolveu" } | ConvertTo-Json)
$remote.status
```

O status final é `resolvido_remotamente`. Esse é o único desfecho que o front-end apresenta como visita evitada de **R$ 200**.

DEMO-REMOTE: acompanhe risco, identificação, checklist, confirmação e a mudança para Economia realizada — R$ 200.

### 2. Encaminhamento urgente — Cheiro de queimado

Abra `DEMO-URGENT` e informe o risco. A regra determinística interrompe a triagem sem aguardar foto, checklist ou confirmação:

```powershell
Invoke-RestMethod -Method Get -Uri "$api/tickets/DEMO-URGENT"
$urgent = Invoke-RestMethod -Method Post -Uri "$api/tickets/DEMO-URGENT/messages" -ContentType "application/json" -Body (@{ content = "Há cheiro de queimado no cooler" } | ConvertTo-Json)
$urgent | Select-Object status, priority, outcome_reason
```

O resultado é `encaminhado_fornecedor`, prioridade `urgente`, sem saving.

DEMO-URGENT: acompanhe a interrupção por risco, prioridade urgente e Economia não realizada — R$ 0.

### 3. Timeout acelerado — Porta não fecha

Coloque `DEMO-DOOR` em confirmação pendente e passe um instante posterior ao deadline. O parâmetro `now` só é aceito porque o back-end desta demonstração foi iniciado com `DEMO_MODE=true`.

```powershell
Invoke-RestMethod -Method Post -Uri "$api/tickets/DEMO-DOOR/messages" -ContentType "application/json" -Body (@{ content = "sim" } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$api/tickets/DEMO-DOOR/equipment/serial" -ContentType "application/json" -Body (@{ modelo = "CX-400"; numero_serie = "BR-DEMO-002" } | ConvertTo-Json)
$waiting = Invoke-RestMethod -Method Post -Uri "$api/tickets/DEMO-DOOR/messages" -ContentType "application/json" -Body (@{ content = "sim, os dados estão corretos" } | ConvertTo-Json)
$demoNow = [DateTimeOffset]::Parse($waiting.confirmation_deadline).AddSeconds(1).ToString("o")
$encodedNow = [Uri]::EscapeDataString($demoNow)
$expiredIds = Invoke-RestMethod -Method Post -Uri "$api/maintenance/expire-confirmations?now=$encodedNow"
$expiredIds
Invoke-RestMethod -Method Get -Uri "$api/tickets/DEMO-DOOR" | Select-Object status, outcome_reason
```

O caso termina como `encaminhado_fornecedor`, com motivo `sem_confirmacao_pdv`, sem esperar 30 minutos e sem contabilizar saving. O `now` acelerado só examina `DEMO-REMOTE`, `DEMO-DOOR`, `DEMO-SUPPLIER` e `DEMO-URGENT`. Sem o parâmetro `now`, a mesma rota usa o relógio real para todos os chamados vencidos; com `now` e `DEMO_MODE` desligado, ela responde HTTP 403. Um valor de `now` malformado responde HTTP 422.

Execute `POST /demo/reset` novamente antes de repetir a apresentação.

## Verificação local

```powershell
Set-Location backend
uv run pytest -v

Set-Location ../agent
uv run pytest tests -v

Set-Location ../frontend
npm test
npm run lint
npm run build
```

O escopo `tests` no agente evita coletar arquivos de teste internos do template em `src/workflow/crews/test_crew/`, que exigem credenciais e não fazem parte da suíte do produto.
