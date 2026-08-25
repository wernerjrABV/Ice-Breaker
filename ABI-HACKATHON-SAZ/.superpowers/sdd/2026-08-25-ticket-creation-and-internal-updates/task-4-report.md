# Task 4 — Cores, rótulos e verificação integrada

## Entrega

- Mensagens internas exibem o rótulo `Atualização interna` e o balão amarelo de alto contraste.
- Mensagens do assistente e do PDV exibem, respectivamente, `Mensagem para o PDV` e `Resposta do PDV`, ambas com fundo branco.
- O contrato TypeScript e o mapa do dashboard agora incluem `initial_triage_started`, `initial_triage_routed_supplier`, `pdv_conversation_started` e `remote_solution_found`.
- O README documenta os assuntos de demonstração para triagem via WhatsApp (sem envio real) e encaminhamento direto ao fornecedor.

## TDD

- Red: `npm test -- Home.test.tsx AgentDashboard.test.tsx` falhou por ausência dos rótulos e do mapa de categorias.
- Green: os mesmos testes passaram após a implementação (40 testes).

## Verificação final

- `frontend/npm test`: 62 passed.
- `frontend/npm run lint`: exit 0.
- `frontend/npm run build`: exit 0.
- `backend/uv run pytest -v --basetemp .pytest-task4-temp`: 142 passed, 1 warning de depreciação externa do Starlette.

O comando padrão de pytest não pôde criar `%LOCALAPPDATA%\\Temp\\pytest-of-werner.junior` (`WinError 5`); a base temporária isolada preservou `backend/data/backend.db`.
