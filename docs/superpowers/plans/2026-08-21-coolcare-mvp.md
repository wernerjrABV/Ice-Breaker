# CoolCare MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir no template do Hackathon um chat de triagem de coolers que lê a etiqueta, executa checklists seguros e encerra remotamente somente após confirmação do PDV; falha, risco ou timeout de 30 minutos encaminham o caso ao fornecedor.

**Architecture:** O React apresenta uma conversa semelhante ao WhatsApp. O FastAPI centraliza estado, persistência SQLite, regras determinísticas e timeout; a API CrewAI interpreta mensagens e lê etiquetas, mas nunca decide sozinha os casos críticos. Os testes isolam chamadas ao modelo com adapters injetáveis.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Vitest, Testing Library, FastAPI, Pydantic, SQLite, pytest e CrewAI 1.3.

**Spec:** `docs/superpowers/specs/2026-08-20-coolcare-mvp-design.md`

## Global Constraints

- Reutilizar o template `ABI-HACKATHON-SAZ` e manter o fluxo `frontend → backend → agent`.
- Atender somente coolers e geladeiras; chopper e postmix ficam fora do MVP.
- Nunca orientar abertura do equipamento, reparo elétrico ou manipulação de componentes internos.
- Somente uma confirmação positiva do PDV produz `resolvido_remotamente` e visita evitada.
- Resposta negativa, risco crítico ou 30 minutos sem confirmação produzem `encaminhado_fornecedor`.
- Cheiro de queimado, faísca, cabo danificado ou vazamento são encaminhados imediatamente.
- A foto da etiqueta faz parte da jornada; quando a leitura não for confiável, solicitar o número de série manualmente.
- Não integrar WhatsApp, Delfos, ticketing ou fornecedor reais no MVP.

---

## File Structure

### Agent

- `ABI-HACKATHON-SAZ/agent/src/workflow/contracts.py`: contratos Pydantic compartilhados pela API do agente.
- `ABI-HACKATHON-SAZ/agent/src/workflow/label_reader.py`: extração multimodal de modelo e serial com adapter de LLM.
- `ABI-HACKATHON-SAZ/agent/src/workflow/conversation.py`: geração estruturada de resposta curta a partir do estado e histórico.
- `ABI-HACKATHON-SAZ/agent/src/workflow/knowledge/cooler_guidance.md`: instruções seguras aprovadas por sintoma.
- `ABI-HACKATHON-SAZ/agent/src/workflow/knowledge/historical_cases.json`: amostra anonimizada de desfechos históricos para contexto da demo.
- `ABI-HACKATHON-SAZ/agent/src/workflow/api.py`: endpoints `/label/read` e `/conversation/respond`.
- `ABI-HACKATHON-SAZ/agent/tests/`: testes sem rede para OCR e conversa.

### Backend

- `ABI-HACKATHON-SAZ/backend/src/models.py`: enums e modelos de API/domínio.
- `ABI-HACKATHON-SAZ/backend/src/triage_rules.py`: normalização de sintomas e regras determinísticas.
- `ABI-HACKATHON-SAZ/backend/src/db.py`: persistência de tickets, mensagens, equipamento e deadline.
- `ABI-HACKATHON-SAZ/backend/src/client.py`: cliente tipado para os dois endpoints do agente.
- `ABI-HACKATHON-SAZ/backend/src/service.py`: máquina de estados da conversa.
- `ABI-HACKATHON-SAZ/backend/src/main.py`: rotas HTTP do MVP.
- `ABI-HACKATHON-SAZ/backend/tests/`: testes unitários e de API.

### Frontend

- `ABI-HACKATHON-SAZ/frontend/src/clients/client.ts`: contratos e chamadas da API CoolCare.
- `ABI-HACKATHON-SAZ/frontend/src/pages/Home/Home.tsx`: tela principal do chat.
- `ABI-HACKATHON-SAZ/frontend/src/pages/Home/Home.css`: layout responsivo semelhante ao WhatsApp.
- `ABI-HACKATHON-SAZ/frontend/src/pages/Home/Home.test.tsx`: jornada principal da interface.
- `ABI-HACKATHON-SAZ/frontend/src/test/setup.ts`: configuração de testes DOM.

### Demo e documentação

- `ABI-HACKATHON-SAZ/backend/src/demo_data.py`: chamados pré-carregados para a apresentação.
- `ABI-HACKATHON-SAZ/README.md`: execução, configuração e roteiro da demo.

---

### Task 1: Motor determinístico de triagem

**Files:**
- Create: `ABI-HACKATHON-SAZ/backend/src/models.py`
- Create: `ABI-HACKATHON-SAZ/backend/src/triage_rules.py`
- Create: `ABI-HACKATHON-SAZ/backend/tests/test_triage_rules.py`
- Modify: `ABI-HACKATHON-SAZ/backend/pyproject.toml`

**Interfaces:**
- Consumes: texto normalizado do assunto/descrição e `set[RiskFlag]` extraído da conversa.
- Produces: `normalize_symptom(text: str) -> Symptom` e `decide_triage(symptom: Symptom, risks: set[RiskFlag]) -> TriageDecision`.

- [ ] **Step 1: Adicionar pytest e escrever os testes das regras**

Adicionar `[dependency-groups] dev = ["pytest>=8.4.0"]` ao `pyproject.toml` e criar:

```python
from src.models import Outcome, Priority, RiskFlag, Symptom
from src.triage_rules import decide_triage, normalize_symptom


def test_normalizes_supported_symptoms():
    assert normalize_symptom("O cooler está congelando bebidas") is Symptom.FREEZING_DRINKS
    assert normalize_symptom("a porta não fecha") is Symptom.DOOR_NOT_CLOSING
    assert normalize_symptom("geladeira não gela") is Symptom.NOT_COOLING
    assert normalize_symptom("equipamento não liga") is Symptom.NOT_POWERING_ON
    assert normalize_symptom("barulho muito alto") is Symptom.ABNORMAL_NOISE


def test_critical_risk_always_routes_urgently():
    result = decide_triage(Symptom.FREEZING_DRINKS, {RiskFlag.BURNING_SMELL})
    assert result.outcome is Outcome.SUPPLIER
    assert result.priority is Priority.URGENT
    assert result.checklist == []


def test_remote_candidate_returns_safe_checklist():
    result = decide_triage(Symptom.FREEZING_DRINKS, set())
    assert result.outcome is Outcome.REMOTE_CHECKLIST
    assert "ajuste de temperatura" in " ".join(result.checklist).lower()


def test_noise_routes_to_supplier():
    result = decide_triage(Symptom.ABNORMAL_NOISE, set())
    assert result.outcome is Outcome.SUPPLIER
    assert result.priority is Priority.NORMAL
```

- [ ] **Step 2: Executar os testes e verificar a falha inicial**

Run: `cd ABI-HACKATHON-SAZ/backend && uv sync && uv run pytest tests/test_triage_rules.py -v`

Expected: FAIL com `ModuleNotFoundError: No module named 'src.models'`.

- [ ] **Step 3: Criar os modelos e a implementação mínima das regras**

```python
# src/models.py
from enum import Enum
from pydantic import BaseModel


class TicketStatus(str, Enum):
    TRIAGE = "em_triagem"
    WAITING_CONFIRMATION = "aguardando_confirmacao"
    REMOTE_RESOLVED = "resolvido_remotamente"
    SUPPLIER = "encaminhado_fornecedor"


class ConversationStage(str, Enum):
    PROXIMITY = "aguardando_proximidade"
    IDENTIFICATION = "aguardando_identificacao"
    DIAGNOSIS = "diagnostico"
    CONFIRMATION = "aguardando_confirmacao"
    FINISHED = "finalizado"


class Symptom(str, Enum):
    FREEZING_DRINKS = "congela_bebidas"
    DOOR_NOT_CLOSING = "porta_nao_fecha"
    NOT_COOLING = "nao_gela"
    NOT_POWERING_ON = "nao_liga"
    ABNORMAL_NOISE = "ruido_anormal"
    UNKNOWN = "desconhecido"


class RiskFlag(str, Enum):
    BURNING_SMELL = "cheiro_queimado"
    SPARK = "faisca"
    DAMAGED_CABLE = "cabo_danificado"
    LEAK = "vazamento"


class Outcome(str, Enum):
    REMOTE_CHECKLIST = "checklist_remoto"
    SUPPLIER = "encaminhado_fornecedor"


class Priority(str, Enum):
    NORMAL = "normal"
    URGENT = "urgente"


class TriageDecision(BaseModel):
    outcome: Outcome
    priority: Priority = Priority.NORMAL
    checklist: list[str] = Field(default_factory=list)
    reason: str
```

Importar `Field` de `pydantic` em `models.py`.

Implementar `normalize_symptom` com correspondências explícitas e `decide_triage` com esta ordem: qualquer risco crítico → fornecedor urgente; ruído ou não liga → fornecedor normal; congela bebidas, porta não fecha ou não gela → checklist seguro; desconhecido → fornecedor normal. Os checklists só podem mencionar ajuste, obstrução/organização, porta/vedação visível, ventilação externa e gelo visível.

- [ ] **Step 4: Executar os testes do motor**

Run: `cd ABI-HACKATHON-SAZ/backend && uv run pytest tests/test_triage_rules.py -v`

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ABI-HACKATHON-SAZ
git add backend/pyproject.toml backend/uv.lock backend/src/models.py backend/src/triage_rules.py backend/tests/test_triage_rules.py
git commit -m "feat: add deterministic cooler triage rules"
```

---

### Task 2: Persistência do atendimento e histórico da conversa

**Files:**
- Modify: `ABI-HACKATHON-SAZ/backend/src/db.py`
- Create: `ABI-HACKATHON-SAZ/backend/tests/test_db.py`

**Interfaces:**
- Consumes: `TicketStatus`, `ConversationStage`, dados básicos do PDV e mensagens.
- Produces: `create_ticket`, `get_ticket`, `append_message`, `set_equipment`, `set_ticket_state` e `list_expired_confirmations`.

- [ ] **Step 1: Escrever testes com banco temporário**

```python
from datetime import datetime, timedelta, timezone
from src import db
from src.models import ConversationStage, TicketStatus


def test_ticket_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.create_ticket("T-1", "Bar do João", "Congela bebidas", "Bebidas congelando")
    db.append_message("T-1", "assistant", "Você está próximo ao equipamento?")
    db.set_equipment("T-1", "CX-400", "BR-12345", 0.98, "label.jpg")
    ticket = db.get_ticket("T-1")
    assert ticket["nome_pdv"] == "Bar do João"
    assert ticket["equipment"]["numero_serie"] == "BR-12345"
    assert ticket["messages"][0]["role"] == "assistant"


def test_lists_only_expired_waiting_confirmations(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.create_ticket("T-2", "Mercado", "Não gela", "")
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.set_ticket_state("T-2", TicketStatus.WAITING_CONFIRMATION, ConversationStage.CONFIRMATION, expired)
    assert [item["id"] for item in db.list_expired_confirmations()] == ["T-2"]
```

- [ ] **Step 2: Executar e confirmar a falha**

Run: `cd ABI-HACKATHON-SAZ/backend && uv run pytest tests/test_db.py -v`

Expected: FAIL porque `create_ticket` e as tabelas novas ainda não existem.

- [ ] **Step 3: Substituir o esquema genérico pelo esquema do CoolCare**

Criar tabelas `tickets`, `messages` e `equipment`. `tickets` deve guardar `status`, `stage`, `confirmation_deadline`, `priority`, `outcome_reason`, `created_at` e `updated_at`. `messages` deve guardar `ticket_id`, `role`, `content`, `kind` e `created_at`. `equipment` deve guardar uma linha por ticket com modelo, serial, confiança e nome da imagem.

Implementar estas assinaturas exatas: `create_ticket(ticket_id: str, nome_pdv: str, assunto: str, descricao_base: str) -> None`; `append_message(ticket_id: str, role: str, content: str, kind: str = "text") -> None`; `set_equipment(ticket_id: str, modelo: str, numero_serie: str, confianca: float, image_name: str | None) -> None`; `set_ticket_state(ticket_id: str, status: TicketStatus, stage: ConversationStage, deadline: datetime | None = None, priority: str = "normal", reason: str = "") -> None`; `get_ticket(ticket_id: str) -> dict[str, object] | None`; e `list_expired_confirmations(now: datetime | None = None) -> list[dict[str, object]]`.

Todas as datas devem ser UTC ISO-8601. Não migrar nem apagar `backend/data/backend.db`; `CREATE TABLE IF NOT EXISTS` preserva o arquivo existente.

- [ ] **Step 4: Executar os testes de persistência**

Run: `cd ABI-HACKATHON-SAZ/backend && uv run pytest tests/test_db.py -v`

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ABI-HACKATHON-SAZ
git add backend/src/db.py backend/tests/test_db.py
git commit -m "feat: persist CoolCare conversations"
```

---

### Task 3: Leitura de etiqueta e resposta estruturada do agente

**Files:**
- Create: `ABI-HACKATHON-SAZ/agent/src/workflow/contracts.py`
- Create: `ABI-HACKATHON-SAZ/agent/src/workflow/label_reader.py`
- Create: `ABI-HACKATHON-SAZ/agent/src/workflow/conversation.py`
- Create: `ABI-HACKATHON-SAZ/agent/src/workflow/knowledge/cooler_guidance.md`
- Create: `ABI-HACKATHON-SAZ/agent/src/workflow/knowledge/historical_cases.json`
- Modify: `ABI-HACKATHON-SAZ/agent/src/workflow/api.py`
- Modify: `ABI-HACKATHON-SAZ/agent/pyproject.toml`
- Create: `ABI-HACKATHON-SAZ/agent/tests/test_agent_services.py`

**Interfaces:**
- Consumes: imagem base64, contexto do ticket, etapa e histórico.
- Produces: `EquipmentLabel(modelo, numero_serie, confianca)` e `ConversationReply(message, risks, symptom)`.

- [ ] **Step 1: Escrever testes usando um LLM fake**

```python
from workflow.contracts import ConversationRequest, EquipmentLabel
from workflow.conversation import generate_reply
from workflow.label_reader import read_label


class FakeLlm:
    def __init__(self, result): self.result = result
    def call(self, **_kwargs): return self.result


def test_reads_label_with_injected_llm():
    expected = EquipmentLabel(modelo="CX-400", numero_serie="BR-12345", confianca=0.98)
    assert read_label("data:image/jpeg;base64,abc", FakeLlm(expected)) == expected


def test_conversation_returns_one_short_question():
    request = ConversationRequest(
        nome_pdv="Bar do João",
        assunto="Não gela",
        stage="diagnostico",
        messages=[],
    )
    result = generate_reply(request, FakeLlm({
        "message": "A porta está fechando completamente?",
        "risks": [],
        "symptom": "nao_gela",
    }))
    assert result.message.count("?") == 1
    assert result.symptom == "nao_gela"
```

- [ ] **Step 2: Executar e confirmar a falha**

Run: `cd ABI-HACKATHON-SAZ/agent && uv sync && uv run pytest tests/test_agent_services.py -v`

Expected: FAIL com módulos `workflow.contracts`, `workflow.label_reader` e `workflow.conversation` ausentes.

- [ ] **Step 3: Implementar contratos e adapters do modelo**

Os contratos devem conter:

```python
from pydantic import BaseModel, Field


class EquipmentLabel(BaseModel):
    modelo: str = ""
    numero_serie: str = ""
    confianca: float = Field(ge=0, le=1)


class ChatMessage(BaseModel):
    role: str
    content: str


class ConversationRequest(BaseModel):
    nome_pdv: str
    assunto: str
    stage: str
    messages: list[ChatMessage]


class ConversationReply(BaseModel):
    message: str
    risks: list[str] = Field(default_factory=list)
    symptom: str = "desconhecido"
```

`read_label(image_data_url, llm=None)` deve montar `messages` com texto e `image_url`, então chamar `llm.call(messages=messages, response_format=EquipmentLabel)` e devolver confiança baixa quando modelo ou serial vierem vazios. `generate_reply(request, llm=None)` deve pedir apenas uma informação por vez, usar português simples e incluir no prompt a proibição de reparos elétricos ou abertura do equipamento. Converter dicts do fake para os modelos Pydantic.

`cooler_guidance.md` deve conter somente os cinco roteiros aprovados e a lista de ações proibidas. `historical_cases.json` deve conter cinco objetos anonimizados no formato `{"symptom":"congela_bebidas","outcome":"resolvido_remotamente","action":"ajuste de temperatura"}`; incluir um exemplo para cada sintoma. `conversation.py` deve carregar ambos com `Path(__file__).parent / "knowledge"` e inserir o conteúdo como contexto, sem permitir que o histórico sobrescreva as regras de segurança.

Expor endpoints tipados:

```python
@app.post("/label/read", response_model=EquipmentLabel)
def label_read(request: LabelReadRequest) -> EquipmentLabel:
    return read_label(request.image_data_url)


@app.post("/conversation/respond", response_model=ConversationReply)
def conversation_respond(request: ConversationRequest) -> ConversationReply:
    return generate_reply(request)
```

Adicionar `[dependency-groups] dev = ["pytest>=8.4.0"]` ao `pyproject.toml` do agente.

- [ ] **Step 4: Executar os testes e a validação de import da API**

Run: `cd ABI-HACKATHON-SAZ/agent && uv run pytest tests/test_agent_services.py -v && uv run python -c "from workflow.api import app; print([r.path for r in app.routes])"`

Expected: 2 tests PASS e saída contendo `/label/read` e `/conversation/respond`.

- [ ] **Step 5: Commit**

```bash
cd ABI-HACKATHON-SAZ
git add agent/pyproject.toml agent/uv.lock agent/src/workflow/contracts.py agent/src/workflow/label_reader.py agent/src/workflow/conversation.py agent/src/workflow/knowledge/cooler_guidance.md agent/src/workflow/knowledge/historical_cases.json agent/src/workflow/api.py agent/tests/test_agent_services.py
git commit -m "feat: add multimodal CoolCare agent services"
```

---

### Task 4: Máquina de estados e API conversacional

**Files:**
- Modify: `ABI-HACKATHON-SAZ/backend/src/client.py`
- Create: `ABI-HACKATHON-SAZ/backend/src/service.py`
- Modify: `ABI-HACKATHON-SAZ/backend/src/main.py`
- Create: `ABI-HACKATHON-SAZ/backend/tests/test_service.py`
- Create: `ABI-HACKATHON-SAZ/backend/tests/test_api.py`

**Interfaces:**
- Consumes: funções de banco da Task 2, `decide_triage` da Task 1 e respostas do agente da Task 3.
- Produces: `create_case`, `handle_text`, `handle_label`, `expire_confirmations` e rotas REST.

- [ ] **Step 1: Escrever testes da jornada e dos endpoints**

```python
# tests/test_service.py
from src import db, service
from src.models import TicketStatus


def test_remote_resolution_requires_explicit_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ticket = service.create_case("Bar do João", "Congela bebidas", "Bebidas congelando")
    service.handle_text(ticket["id"], "sim")
    service.handle_serial(ticket["id"], "CX-400", "BR-12345")
    waiting = db.get_ticket(ticket["id"])
    assert waiting["status"] == TicketStatus.WAITING_CONFIRMATION.value
    service.handle_text(ticket["id"], "sim, resolveu")
    resolved = db.get_ticket(ticket["id"])
    assert resolved["status"] == TicketStatus.REMOTE_RESOLVED.value


def test_negative_confirmation_routes_supplier(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ticket = service.create_case("Bar", "Não gela", "")
    service.handle_text(ticket["id"], "sim")
    service.handle_serial(ticket["id"], "CX-400", "BR-1")
    service.handle_text(ticket["id"], "não resolveu")
    assert db.get_ticket(ticket["id"])["status"] == TicketStatus.SUPPLIER.value
```

O teste de API deve criar um ticket com `POST /tickets`, recuperar com `GET /tickets/{id}`, responder com `POST /tickets/{id}/messages` e validar HTTP 404 para id inexistente.

- [ ] **Step 2: Executar e confirmar a falha**

Run: `cd ABI-HACKATHON-SAZ/backend && uv run pytest tests/test_service.py tests/test_api.py -v`

Expected: FAIL porque `src.service` e as rotas `/tickets` ainda não existem.

- [ ] **Step 3: Implementar o cliente, a máquina de estados e as rotas**

O cliente deve expor as assinaturas exatas `read_equipment_label(image_data_url: str) -> dict[str, Any]` e `request_conversation_reply(payload: dict[str, Any]) -> dict[str, Any]`; ambas fazem `POST`, chamam `raise_for_status()` e retornam `response.json()`.

A máquina de estados deve seguir esta sequência:

```text
create_case → aguardando_proximidade
"sim" → aguardando_identificacao
"não" → mantém aguardando_proximidade e informa que o atendimento pode ser retomado quando o PDV estiver junto ao cooler
foto ou serial → diagnóstico determinístico
checklist remoto → aguardando_confirmacao + deadline UTC de 30 minutos
confirmação positiva → resolvido_remotamente
confirmação negativa → encaminhado_fornecedor
risco ou caso técnico → encaminhado_fornecedor imediatamente
```

A mensagem inicial deve ser gerada exatamente pelo backend com nome do PDV e assunto. Usar a IA somente para interpretação/variação das perguntas; a transição de estado permanece no `service.py`.

Expor:

```python
POST /tickets
GET /tickets/{ticket_id}
POST /tickets/{ticket_id}/messages
POST /tickets/{ticket_id}/equipment/serial
POST /tickets/{ticket_id}/equipment/photo
POST /maintenance/expire-confirmations
```

O upload de foto recebe `UploadFile`, converte bytes para data URL, chama `/label/read` e exige serial manual quando `confianca < 0.80` ou o serial estiver vazio. Adicionar `python-multipart` às dependências do backend.

- [ ] **Step 4: Executar testes backend completos**

Run: `cd ABI-HACKATHON-SAZ/backend && uv sync && uv run pytest -v`

Expected: todos os testes PASS, sem chamadas reais à rede.

- [ ] **Step 5: Commit**

```bash
cd ABI-HACKATHON-SAZ
git add backend/pyproject.toml backend/uv.lock backend/src/client.py backend/src/service.py backend/src/main.py backend/tests/test_service.py backend/tests/test_api.py
git commit -m "feat: add CoolCare conversational API"
```

---

### Task 5: Timeout e encaminhamento completo ao fornecedor

**Files:**
- Modify: `ABI-HACKATHON-SAZ/backend/src/service.py`
- Modify: `ABI-HACKATHON-SAZ/backend/src/db.py`
- Create: `ABI-HACKATHON-SAZ/backend/tests/test_timeout.py`

**Interfaces:**
- Consumes: tickets em `aguardando_confirmacao` com `confirmation_deadline` vencido.
- Produces: `expire_confirmations(now: datetime | None = None) -> list[str]` e `supplier_summary(ticket_id: str) -> dict[str, object]`.

- [ ] **Step 1: Escrever o teste do timeout e do resumo**

```python
from datetime import datetime, timedelta, timezone
from src import db, service
from src.models import ConversationStage, TicketStatus


def test_timeout_routes_and_builds_supplier_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ticket = service.create_case("Mercado Central", "Não gela", "Baixa refrigeração")
    db.set_equipment(ticket["id"], "CX-400", "BR-9", 1.0, None)
    db.append_message(ticket["id"], "assistant", "Verifique se a porta fecha.")
    deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.set_ticket_state(ticket["id"], TicketStatus.WAITING_CONFIRMATION, ConversationStage.CONFIRMATION, deadline)
    assert service.expire_confirmations() == [ticket["id"]]
    summary = service.supplier_summary(ticket["id"])
    assert summary["motivo"] == "sem_confirmacao_pdv"
    assert summary["numero_serie"] == "BR-9"
    assert summary["acoes_tentadas"] == ["Verifique se a porta fecha."]
```

- [ ] **Step 2: Executar e confirmar a falha**

Run: `cd ABI-HACKATHON-SAZ/backend && uv run pytest tests/test_timeout.py -v`

Expected: FAIL porque `expire_confirmations` e `supplier_summary` ainda não existem.

- [ ] **Step 3: Implementar expiração idempotente e resumo**

`expire_confirmations` deve consultar apenas tickets ainda aguardando confirmação, marcar cada um como `encaminhado_fornecedor/finalizado`, gravar `sem_confirmacao_pdv` e devolver os ids alterados. Uma segunda execução com o mesmo horário deve devolver `[]`.

`supplier_summary` deve devolver:

```python
{
    "ticket_id": ticket_id,
    "nome_pdv": ticket["nome_pdv"],
    "assunto": ticket["assunto"],
    "modelo": ticket["equipment"]["modelo"],
    "numero_serie": ticket["equipment"]["numero_serie"],
    "prioridade": ticket["priority"],
    "motivo": ticket["outcome_reason"],
    "acoes_tentadas": assistant_checklist_messages,
}
```

- [ ] **Step 4: Executar toda a suíte backend**

Run: `cd ABI-HACKATHON-SAZ/backend && uv run pytest -v`

Expected: todos os testes PASS, incluindo idempotência do timeout.

- [ ] **Step 5: Commit**

```bash
cd ABI-HACKATHON-SAZ
git add backend/src/service.py backend/src/db.py backend/tests/test_timeout.py
git commit -m "feat: route confirmation timeouts to supplier"
```

---

### Task 6: Cliente TypeScript e base de testes do front-end

**Files:**
- Modify: `ABI-HACKATHON-SAZ/frontend/package.json`
- Modify: `ABI-HACKATHON-SAZ/frontend/src/clients/client.ts`
- Create: `ABI-HACKATHON-SAZ/frontend/src/clients/client.test.ts`
- Create: `ABI-HACKATHON-SAZ/frontend/src/test/setup.ts`
- Modify: `ABI-HACKATHON-SAZ/frontend/vite.config.ts`

**Interfaces:**
- Consumes: endpoints REST da Task 4.
- Produces: tipos `Ticket`, `Message`, `Equipment` e funções `createTicket`, `getTicket`, `sendMessage`, `sendSerial`, `sendPhoto`, `expireConfirmations`.

- [ ] **Step 1: Configurar Vitest e escrever teste do cliente**

Adicionar `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom` e `@testing-library/user-event` às devDependencies e script `"test": "vitest run"`.

```typescript
import { afterEach, expect, test, vi } from 'vitest'
import { createTicket } from './client'

afterEach(() => vi.restoreAllMocks())

test('creates a ticket with the base call information', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ id: 'T-1' }), { status: 201 })
  )
  await expect(createTicket('Bar do João', 'Não gela', 'Baixa refrigeração')).resolves.toEqual({ id: 'T-1' })
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/tickets'), expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ nome_pdv: 'Bar do João', assunto: 'Não gela', descricao_base: 'Baixa refrigeração' }),
  }))
})
```

- [ ] **Step 2: Executar e confirmar a falha**

Run: `cd ABI-HACKATHON-SAZ/frontend && npm install && npm test`

Expected: FAIL porque `createTicket` não existe.

- [ ] **Step 3: Implementar contratos e chamadas tipadas**

```typescript
export type TicketStatus = 'em_triagem' | 'aguardando_confirmacao' | 'resolvido_remotamente' | 'encaminhado_fornecedor'
export interface Message { id: number; role: 'user' | 'assistant'; content: string; kind: 'text' | 'image'; created_at: string }
export interface Equipment { modelo: string; numero_serie: string; confianca: number; image_name: string | null }
export interface Ticket {
  id: string
  nome_pdv: string
  assunto: string
  descricao_base: string
  status: TicketStatus
  stage: string
  confirmation_deadline: string | null
  equipment: Equipment | null
  messages: Message[]
  supplier_summary?: Record<string, unknown>
}
```

Todas as funções devem verificar `response.ok` e lançar mensagens em português contendo o status HTTP.

- [ ] **Step 4: Executar testes, lint e build**

Run: `cd ABI-HACKATHON-SAZ/frontend && npm test && npm run lint && npm run build`

Expected: tests PASS, lint sem erros e build concluído.

- [ ] **Step 5: Commit**

```bash
cd ABI-HACKATHON-SAZ
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/src/test/setup.ts frontend/src/clients/client.ts frontend/src/clients/client.test.ts
git commit -m "feat: add typed CoolCare frontend client"
```

---

### Task 7: Chat estilo WhatsApp e estados visíveis

**Files:**
- Modify: `ABI-HACKATHON-SAZ/frontend/src/pages/Home/Home.tsx`
- Modify: `ABI-HACKATHON-SAZ/frontend/src/pages/Home/Home.css`
- Modify: `ABI-HACKATHON-SAZ/frontend/src/index.css`
- Modify: `ABI-HACKATHON-SAZ/frontend/src/components/Header/Header.tsx`
- Create: `ABI-HACKATHON-SAZ/frontend/src/pages/Home/Home.test.tsx`

**Interfaces:**
- Consumes: cliente da Task 6.
- Produces: jornada completa de criação, resposta rápida, texto, foto/serial e exibição do resultado.

- [ ] **Step 1: Escrever testes das duas jornadas principais**

Mockar o módulo `../../clients/client` e criar testes com Testing Library:

```typescript
test('starts with the proactive message and asks for equipment identification', async () => {
  render(<Home />)
  expect(await screen.findByText(/quero entender melhor.*ajudar você agora/i)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /^sim$/i }))
  expect(await screen.findByText(/foto da etiqueta.*número de série/i)).toBeInTheDocument()
})

test('shows remote saving only after positive confirmation', async () => {
  mockTicket.status = 'aguardando_confirmacao'
  render(<Home />)
  expect(screen.queryByText(/R\$ 200/)).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /sim, resolveu/i }))
  expect(await screen.findByText(/resolvido remotamente/i)).toBeInTheDocument()
  expect(screen.getByText(/R\$ 200/)).toBeInTheDocument()
})
```

Adicionar também teste de `encaminhado_fornecedor` sem exibir saving e de fallback para serial manual quando confiança do OCR for menor que 0,80.

- [ ] **Step 2: Executar e confirmar a falha**

Run: `cd ABI-HACKATHON-SAZ/frontend && npm test -- Home.test.tsx`

Expected: FAIL porque a página ainda é o formulário do template.

- [ ] **Step 3: Implementar a tela do chat**

A tela deve conter:

```text
Cabeçalho: CoolCare · Assistente de manutenção
Contexto: nome do PDV + assunto do chamado
Área de mensagens com balões do agente e do PDV
Respostas rápidas “Sim”, “Não” e “Sim, resolveu” quando aplicáveis
Input de texto e botão de envio
Botão de foto com input file accept="image/*" capture="environment"
Formulário de serial manual quando OCR não for confiável
Faixa de status e contador visual até o limite de confirmação
Card final: resolvido remotamente + R$ 200, ou encaminhado ao fornecedor + resumo
```

Manter o estado do ticket no componente e atualizar via `getTicket` após cada ação. Desabilitar controles durante requests. Em telas até 720 px, ocupar toda a largura; em desktop, simular um aparelho central com largura máxima de 520 px. Usar paleta clara com verde para o chat e vermelho somente em avisos urgentes.

- [ ] **Step 4: Executar testes e verificações front-end**

Run: `cd ABI-HACKATHON-SAZ/frontend && npm test && npm run lint && npm run build`

Expected: todos os testes PASS, lint sem erros e build concluído.

- [ ] **Step 5: Commit**

```bash
cd ABI-HACKATHON-SAZ
git add frontend/src/pages/Home/Home.tsx frontend/src/pages/Home/Home.css frontend/src/pages/Home/Home.test.tsx frontend/src/index.css frontend/src/components/Header/Header.tsx
git commit -m "feat: build CoolCare WhatsApp-style triage chat"
```

---

### Task 8: Dados de demonstração, roteiro e verificação ponta a ponta

**Files:**
- Create: `ABI-HACKATHON-SAZ/backend/src/demo_data.py`
- Modify: `ABI-HACKATHON-SAZ/backend/src/main.py`
- Modify: `ABI-HACKATHON-SAZ/README.md`
- Create: `ABI-HACKATHON-SAZ/backend/tests/test_demo_data.py`

**Interfaces:**
- Consumes: API e máquina de estados concluídas.
- Produces: `seed_demo_cases() -> list[str]` e quatro chamados repetíveis para apresentação.

- [ ] **Step 1: Escrever o teste das fixtures**

```python
from src import db
from src.demo_data import seed_demo_cases


def test_seed_creates_four_repeatable_demo_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    first = seed_demo_cases()
    second = seed_demo_cases()
    assert first == second
    assert len(first) == 4
    assert {db.get_ticket(item)["assunto"] for item in first} == {
        "Congela bebidas", "Porta não fecha", "Não liga", "Cheiro de queimado"
    }
```

- [ ] **Step 2: Executar e confirmar a falha**

Run: `cd ABI-HACKATHON-SAZ/backend && uv run pytest tests/test_demo_data.py -v`

Expected: FAIL porque `src.demo_data` não existe.

- [ ] **Step 3: Criar dados idempotentes e documentar a demo**

Criar ids fixos `DEMO-REMOTE`, `DEMO-DOOR`, `DEMO-SUPPLIER` e `DEMO-URGENT`. `seed_demo_cases` só insere cada caso se ele ainda não existir. Expor `POST /demo/reset` para recriar o estado lógico dos casos sem apagar outros tickets.

Atualizar o README com:

```text
1. Copiar os três .env.example para .env e preencher OPENAI_API_KEY/OPENAI_MODEL.
2. Iniciar agent em :8000, backend em :8001 e frontend em :5173.
3. Abrir DEMO-REMOTE e concluir “Congela bebidas” com confirmação positiva.
4. Abrir DEMO-URGENT e informar cheiro de queimado para encaminhamento imediato.
5. Usar /maintenance/expire-confirmations para demonstrar o timeout sem aguardar 30 minutos, passando um `now` de demonstração aceito apenas quando `DEMO_MODE=true`.
6. Mostrar que somente o caso confirmado contabiliza R$ 200 de visita evitada.
```

- [ ] **Step 4: Executar verificação final completa**

Run: `cd ABI-HACKATHON-SAZ/backend && uv run pytest -v`

Expected: todos os testes backend PASS.

Run: `cd ABI-HACKATHON-SAZ/agent && uv run pytest -v`

Expected: todos os testes agent PASS.

Run: `cd ABI-HACKATHON-SAZ/frontend && npm test && npm run lint && npm run build`

Expected: todos os testes PASS, lint sem erros e build concluído.

Run com as três APIs iniciadas: `Invoke-RestMethod -Method Post http://127.0.0.1:8001/demo/reset`

Expected: JSON com os quatro ids de demonstração.

- [ ] **Step 5: Commit**

```bash
cd ABI-HACKATHON-SAZ
git add backend/src/demo_data.py backend/src/main.py backend/tests/test_demo_data.py README.md
git commit -m "docs: add repeatable CoolCare demo"
```

---

## Final Acceptance Checklist

- [ ] A abertura menciona o nome do PDV, o assunto, a intenção de entender melhor e a possibilidade de ajudar agora.
- [ ] O agente pergunta se o usuário está próximo antes de solicitar foto/serial.
- [ ] Foto de etiqueta com confiança suficiente identifica e confirma modelo/serial.
- [ ] OCR incerto solicita serial manualmente.
- [ ] Os cinco sintomas aprovados seguem as regras determinísticas.
- [ ] Qualquer risco crítico encaminha imediatamente ao fornecedor.
- [ ] Checklist seguro nunca sugere abertura ou reparo elétrico.
- [ ] Saving de BRL 200 aparece somente após confirmação positiva.
- [ ] Resposta negativa e timeout de 30 minutos encaminham ao fornecedor.
- [ ] O resumo ao fornecedor contém PDV, equipamento, evidências, ações e motivo.
- [ ] Testes backend, agent e frontend passam; lint e build do frontend passam.
