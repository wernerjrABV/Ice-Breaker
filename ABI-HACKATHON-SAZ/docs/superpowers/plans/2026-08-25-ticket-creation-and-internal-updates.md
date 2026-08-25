# Abertura de Chamado e Atualizações Internas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Abrir chamados por assunto livre e mostrar decisões internas amarelas e mensagens externas brancas.

**Architecture:** A API nova recebe apenas o assunto e aplica regras determinísticas para fornecedor ou WhatsApp. A tabela de mensagens é mantida: `role=internal` e `kind=internal_status` representam notas operacionais que não entram no payload do agente. Uma rota inicial cria o ticket e `Home` acompanha somente IDs existentes.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLite, pytest, React 19, TypeScript, Vite e Vitest.

**Spec:** `docs/superpowers/specs/2026-08-25-ticket-creation-and-internal-updates-design.md`

## Global Constraints

- Não modificar nem versionar `backend/data/backend.db`.
- `POST /tickets` permanece compatível; a tela nova usa `POST /demo/tickets` com somente `{"assunto": string}`.
- O PDV é `PDV Demonstração`; `descricao_base` repete o assunto e `equipment_type` é `cooler`.
- Atualizações internas: `role=internal`, `kind=internal_status`, amarelo e rótulo `Atualização interna`.
- Mensagens `assistant` e `user` são externas, brancas, com rótulos `Mensagem para o PDV` e `Resposta do PDV`.
- Notas internas nunca entram no payload do agente nem nas evidências do fornecedor.
- Ordem da decisão: risco > fornecedor/visita/troca ou sintoma sem roteiro remoto > contato para `congela bebidas`, `porta não fecha` e `não gela`.
- Textos obrigatórios: `Enviado ao agente para primeira triagem`, `Enviado para o fornecedor`, `Iniciou conversa com o PDV`, `Não encontrou solução; atendimento seguirá com o fornecedor`, `Solução encontrada pelo agente`.
- Não introduzir chamada real ao WhatsApp.

---

### Task 1: Contrato, regras e criação inicial no backend

**Files:**
- Modify: `backend/src/models.py`
- Modify: `backend/src/triage_rules.py`
- Modify: `backend/src/service.py`
- Test: `backend/tests/test_service.py`
- Test: `backend/tests/test_ticket_events.py`

**Interfaces:**
- Produz `InitialTriageDecision(requires_pdv_contact: bool, priority: Priority, reason: str)`.
- Produz `decide_initial_triage(subject: str) -> InitialTriageDecision`.
- Produz `service.create_demo_case(subject: str) -> dict[str, Any]`.

- [ ] **Step 1: Escrever testes de falha para as decisões iniciais**

```python
def test_demo_case_starts_pdv_conversation_for_remote_symptom():
    ticket = service.create_demo_case("Cooler não gela")
    assert [message["content"] for message in ticket["messages"][:2]] == [
        "Enviado ao agente para primeira triagem",
        "Iniciou conversa com o PDV",
    ]
    assert ticket["messages"][0]["role"] == "internal"
    assert ticket["status"] == TicketStatus.TRIAGE.value

def test_demo_case_routes_risk_without_customer_message():
    ticket = service.create_demo_case("Cooler com cheiro de queimado")
    assert ticket["status"] == TicketStatus.SUPPLIER.value
    assert [message["content"] for message in ticket["messages"]] == [
        "Enviado ao agente para primeira triagem",
        "Enviado para o fornecedor",
    ]
```

- [ ] **Step 2: Confirmar que os testes falham**

Run: `Set-Location backend; uv run pytest tests/test_service.py -k "demo_case" -v`

Expected: FAIL porque `create_demo_case` não existe.

- [ ] **Step 3: Implementar o contrato e a criação mínima**

```python
@dataclass(frozen=True)
class InitialTriageDecision:
    requires_pdv_contact: bool
    priority: Priority
    reason: str

def create_demo_case(subject: str) -> dict[str, Any]:
    return create_case("PDV Demonstração", subject, subject, EquipmentType.COOLER,
                       initial_triage=True)
```

Adicionar `internal` a `TicketMessage.role`, `internal_status` aos kinds, as categorias `initial_triage_started`, `initial_triage_routed_supplier`, `pdv_conversation_started`, `remote_solution_found` e whitelists para `reason`, `priority` e `requires_pdv_contact`. Implementar regra determinística e, em `create_case(..., initial_triage=True)`, persistir as notas antes de abrir a conversa ou finalizar.

- [ ] **Step 4: Verificar serviço e eventos**

Run: `Set-Location backend; uv run pytest tests/test_service.py tests/test_ticket_events.py -v`

Expected: PASS, com eventos sem texto integral do assunto.

- [ ] **Step 5: Escrever teste de falha e filtrar notas internas**

```python
def test_agent_payload_omits_internal_messages(monkeypatch):
    ticket = service.create_demo_case("Cooler não gela")
    captured = {}
    def reply(payload):
        captured["payload"] = payload
        return {"reply_key": "confirmar_proximidade", "risks": [], "symptom": "nao_gela"}
    monkeypatch.setattr(service.client, "request_conversation_reply", reply)
    service.handle_text(ticket["id"], "talvez")
    assert all(message["role"] != "internal" for message in captured["payload"]["messages"])
```

Em `_agent_reply`, filtrar para `role in {"assistant", "user"}`. Em `_route_supplier`, inserir a nota inicial ou de falta de solução antes da mensagem externa. Na confirmação positiva, inserir `Solução encontrada pelo agente` antes da mensagem que declare que o problema foi corrigido e o chamado fechado.

Run: `Set-Location backend; uv run pytest -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/models.py backend/src/triage_rules.py backend/src/service.py backend/tests/test_service.py backend/tests/test_ticket_events.py
git commit -m "feat: add initial ticket triage"
```

### Task 2: Endpoint demonstrativo e cliente HTTP

**Files:**
- Modify: `backend/src/main.py`
- Modify: `backend/tests/test_api.py`
- Modify: `frontend/src/clients/client.ts`
- Test: `frontend/src/clients/client.test.ts`

**Interfaces:**
- Consome `service.create_demo_case(subject)`.
- Produz `POST /demo/tickets` com `{"assunto": string}` e status 201.
- Produz `createDemoTicket(assunto: string): Promise<{ id: string }>`.

- [ ] **Step 1: Escrever testes de falha**

```python
def test_demo_ticket_api_accepts_only_subject_and_uses_fixed_pdv(api):
    response = api.post("/demo/tickets", json={"assunto": "Cooler não gela"})
    assert response.status_code == 201
    assert response.json()["nome_pdv"] == "PDV Demonstração"

def test_demo_ticket_api_rejects_blank_subject(api):
    assert api.post("/demo/tickets", json={"assunto": "  "}).status_code == 422
```

```ts
test('createDemoTicket posts only the free subject', async () => {
  await createDemoTicket('Cooler não gela')
  expect(fetch).toHaveBeenCalledWith(
    'http://127.0.0.1:8001/demo/tickets',
    expect.objectContaining({ body: JSON.stringify({ assunto: 'Cooler não gela' }) }),
  )
})
```

- [ ] **Step 2: Confirmar falha**

Run: `Set-Location backend; uv run pytest tests/test_api.py -k "demo_ticket" -v; Set-Location ../frontend; npm test -- client.test.ts`

Expected: FAIL por rota e helper inexistentes.

- [ ] **Step 3: Implementar request, rota e helper**

```python
class CreateDemoTicketRequest(BaseModel):
    assunto: str = Field(min_length=1, max_length=500)

    @field_validator("assunto")
    @classmethod
    def strip_subject(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O assunto é obrigatório.")
        return value

@app.post("/demo/tickets", status_code=201, response_model=TicketResponse)
def create_demo_ticket(request: CreateDemoTicketRequest) -> TicketResponse:
    return _present_ticket(service.create_demo_case(request.assunto))
```

Manter `createTicket`; acrescentar `createDemoTicket`; atualizar as uniões de `Message` com `internal` e `internal_status`.

- [ ] **Step 4: Verificar e commitar**

Run: `Set-Location backend; uv run pytest tests/test_api.py -k "demo_ticket" -v; Set-Location ../frontend; npm test -- client.test.ts`

Expected: PASS.

```powershell
git add backend/src/main.py backend/tests/test_api.py frontend/src/clients/client.ts frontend/src/clients/client.test.ts
git commit -m "feat: expose demo ticket creation"
```

### Task 3: Tela de abertura e carregamento por ID

**Files:**
- Create: `frontend/src/pages/NewTicket/NewTicket.tsx`
- Create: `frontend/src/pages/NewTicket/NewTicket.css`
- Create: `frontend/src/pages/NewTicket/NewTicket.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/Home/Home.tsx`
- Modify: `frontend/src/pages/Home/Home.test.tsx`

**Interfaces:**
- Consome `createDemoTicket(assunto)`.
- Produz rota `/` e navegação para `/home?ticketId=<id>`.
- Faz `Home` carregar somente ticket existente, sem criação automática.

- [ ] **Step 1: Escrever testes de falha**

```tsx
test('opens a ticket from a single free-subject field', async () => {
  render(<NewTicket />)
  await user.type(screen.getByLabelText('Descreva o chamado'), 'Cooler não gela')
  await user.click(screen.getByRole('button', { name: 'Enviar para triagem' }))
  expect(createDemoTicket).toHaveBeenCalledWith('Cooler não gela')
})

test('does not create a ticket when Home has no ticketId', async () => {
  render(<Home />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Abra um chamado')
  expect(createTicket).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: Confirmar falha**

Run: `Set-Location frontend; npm test -- NewTicket.test.tsx Home.test.tsx`

Expected: FAIL porque a página e a remoção do startup automático não existem.

- [ ] **Step 3: Implementar rota e formulário acessível**

```tsx
<label htmlFor="ticket-subject">Descreva o chamado</label>
<textarea id="ticket-subject" required value={subject} onChange={event => setSubject(event.target.value)} />
<button type="submit" disabled={!subject.trim() || busy}>Enviar para triagem</button>
```

Exibir `PDV Demonstração` como texto. Em sucesso, usar `useNavigate()` para montar `/home?ticketId=` mais o ID codificado. Em erro, preservar assunto e usar `role="alert"`. Remover `DEMO_TICKET`, `requestStartup` e criação automática em `Home`; sem ID, renderizar alerta e link para `/`.

- [ ] **Step 4: Verificar e commitar**

Run: `Set-Location frontend; npm test -- NewTicket.test.tsx Home.test.tsx`

Expected: PASS.

```powershell
git add frontend/src/App.tsx frontend/src/pages/NewTicket frontend/src/pages/Home/Home.tsx frontend/src/pages/Home/Home.test.tsx
git commit -m "feat: add ticket opening page"
```

### Task 4: Cores, rótulos e verificação integrada

**Files:**
- Modify: `frontend/src/pages/Home/Home.tsx`
- Modify: `frontend/src/pages/Home/Home.css`
- Modify: `frontend/src/pages/Home/Home.test.tsx`
- Modify: `frontend/src/components/AgentDashboard/eventPresentation.ts`
- Modify: `frontend/src/components/AgentDashboard/AgentDashboard.test.tsx`
- Modify: `README.md`

**Interfaces:**
- Consome `role=internal|assistant|user`.
- Produz balões amarelos para notas internas e brancos para mensagens externas.
- Produz textos de painel para as categorias de evento novas.

- [ ] **Step 1: Escrever teste de falha de apresentação**

```tsx
test('labels internal updates and keeps external messages white', async () => {
  client.getTicket.mockResolvedValue(ticket({ messages: [
    message('internal', 'Iniciou conversa com o PDV', 'internal_status'),
    message('assistant', 'Você está próximo ao equipamento?', 'opening'),
    message('user', 'Sim', 'text'),
  ] }))
  render(<Home />)
  expect(await screen.findByText('Atualização interna')).toBeInTheDocument()
  expect(screen.getByText('Mensagem para o PDV')).toBeInTheDocument()
  expect(screen.getByText('Resposta do PDV')).toBeInTheDocument()
})
```

- [ ] **Step 2: Confirmar falha**

Run: `Set-Location frontend; npm test -- Home.test.tsx AgentDashboard.test.tsx`

Expected: FAIL porque `internal` não tem rótulo nem estilo dedicado.

- [ ] **Step 3: Implementar apresentação e documentação**

```tsx
const messageLabel = item.role === 'internal'
  ? 'Atualização interna'
  : item.role === 'assistant' ? 'Mensagem para o PDV' : 'Resposta do PDV'
```

Renderizar `messageLabel` em `<span className="message-origin">`. Remover verde de `.chat-bubble-user`; manter `#fff` em `assistant` e `user`; criar `.chat-bubble-internal` amarelo de alto contraste. Atualizar `eventPresentation.ts` para as quatro categorias novas e documentar no README os assuntos `Cooler não gela` (WhatsApp) e `Cheiro de queimado no cooler` (fornecedor direto).

- [ ] **Step 4: Verificação final e commit**

Run: `Set-Location frontend; npm test; npm run lint; npm run build; Set-Location ../backend; uv run pytest -v`

Expected: todos os comandos terminam com código 0.

```powershell
git add frontend/src/pages/Home/Home.tsx frontend/src/pages/Home/Home.css frontend/src/pages/Home/Home.test.tsx frontend/src/components/AgentDashboard/eventPresentation.ts frontend/src/components/AgentDashboard/AgentDashboard.test.tsx README.md
git commit -m "feat: distinguish internal ticket updates"
```

