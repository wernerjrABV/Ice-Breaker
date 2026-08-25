import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import type { Ticket, TicketEvent } from '../../clients/client'
import { AgentDashboard } from './AgentDashboard'
import { savingPresentation } from './AgentMetrics'
import { eventCategoryLabels } from './eventPresentation'

afterEach(cleanup)

const waitingTicket: Ticket = {
  id: 'T-DEMO-001',
  nome_pdv: 'Bar do Jo\u00e3o',
  assunto: 'Bebidas congelando',
  descricao_base: 'Bebidas congelando no cooler.',
  equipment_type: 'cooler',
  status: 'aguardando_confirmacao',
  stage: 'aguardando_confirmacao',
  confirmation_deadline: null,
  priority: 'normal',
  outcome_reason: 'aguardando_confirmacao_pdv',
  equipment: {
    modelo: 'CX-400',
    numero_serie: 'BR-DEMO-001',
    confianca: 0.96,
    image_name: 'etiqueta.jpg',
  },
  messages: [],
  supplier_summary: null,
}

function event(id: number): TicketEvent {
  return {
    id,
    ticket_id: waitingTicket.id,
    category: 'triage_decision',
    title: id === 1 ? 'Chamado recebido' : 'Decis\u00e3o do agente',
    description: id === 1 ? 'O agente iniciou a triagem.' : 'Checklist recomendado.',
    state: id === 1 ? 'completed' : 'active',
    metadata: {
      symptom: 'congela_bebidas',
      outcome: 'aguardando_confirmacao_pdv',
      priority: 'normal',
    },
    created_at: `2026-08-25T12:00:0${id}Z`,
  }
}

test.each([
  ['em_triagem', 'Economia potencial', 'R$ 200', 'Ainda n\u00e3o contabilizada'],
  ['aguardando_confirmacao', 'Economia potencial', 'R$ 200', 'Ainda n\u00e3o contabilizada'],
  ['resolvido_remotamente', 'Economia realizada', 'R$ 200', 'Visita t\u00e9cnica evitada'],
  ['encaminhado_fornecedor', 'Economia n\u00e3o realizada', 'R$ 0', 'Atendimento encaminhado'],
] as const)('derives saving only from status %s', (status, label, value, note) => {
  expect(savingPresentation(status)).toMatchObject({ label, value, note })
})

test.each([
  ['initial_triage_started', 'Triagem inicial iniciada'],
  ['initial_triage_routed_supplier', 'Encaminhamento inicial ao fornecedor'],
  ['pdv_conversation_started', 'Conversa com o PDV iniciada'],
  ['remote_solution_found', 'Solução remota encontrada'],
] as const)('presents the new event category %s in Portuguese', (category, label) => {
  expect(eventCategoryLabels[category]).toBe(label)
})

test('uses the mapped label for new categories while preserving unknown event titles', () => {
  const initialTriage = {
    ...event(2),
    category: 'initial_triage_started' as const,
    title: 'Título técnico do backend',
  }
  const future = {
    ...event(1),
    category: 'future_event' as TicketEvent['category'],
    title: 'Título futuro do backend',
  }

  render(<AgentDashboard ticket={waitingTicket} events={[initialTriage, future]} connection="active" />)

  expect(screen.getAllByText('Triagem inicial iniciada')).toHaveLength(2)
  expect(screen.getByText('Título futuro do backend')).toBeInTheDocument()
  expect(screen.queryByText('Título técnico do backend')).not.toBeInTheDocument()
})

test('renders decision focus, safe signals, and chronological events', () => {
  render(<AgentDashboard ticket={waitingTicket} events={[event(2), event(1)]} connection="active" />)

  expect(screen.getByRole('region', { name: 'Intelig\u00eancia do agente' })).toBeInTheDocument()
  expect(screen.getByText('Agente ativo')).toBeInTheDocument()
  expect(screen.getByRole('list', { name: 'Linha do tempo do agente' })).toHaveTextContent('Chamado recebido')
  expect(screen.getByText('congela_bebidas')).toBeInTheDocument()
  expect(screen.getByText('R$ 200')).toBeInTheDocument()
})

test('groups the full history with the newest event above safe signals', () => {
  const { container } = render(
    <AgentDashboard ticket={waitingTicket} events={[event(2), event(1)]} connection="active" />,
  )

  const grid = container.querySelector('.agent-dashboard-grid')
  const timeline = screen.getByRole('region', { name: 'Histórico completo' })
  const focus = screen.getByRole('region', { name: 'Decisão em foco' })
  const signals = screen.getByRole('region', { name: 'Base da decisão' })

  expect(grid).toContainElement(timeline)
  expect(grid).toContainElement(focus)
  expect(grid).toContainElement(signals)
  expect(Array.from(grid?.children ?? [])).toEqual([timeline, focus, signals])
})

test('keeps known event copy for an unknown future category', () => {
  const future = { ...event(3), category: 'future_event' as TicketEvent['category'], title: 'Nova etapa', description: 'Evento compat\u00edvel.' }
  render(<AgentDashboard ticket={waitingTicket} events={[future]} connection="active" />)

  expect(screen.getAllByText('Nova etapa')).toHaveLength(2)
  expect(screen.getAllByText('Evento compat\u00edvel.')).toHaveLength(2)
})

test('shows reconnecting without removing the last events', () => {
  render(<AgentDashboard ticket={waitingTicket} events={[event(1)]} connection="reconnecting" />)
  expect(screen.getByText('Reconectando')).toBeInTheDocument()
  expect(screen.getAllByText('Chamado recebido')).toHaveLength(2)
})

test('shows an availability error in the complete history without hiding recorded events', () => {
  render(
    <AgentDashboard
      ticket={waitingTicket}
      events={[event(1)]}
      connection="reconnecting"
      error="Acompanhamento temporariamente indisponível."
    />,
  )

  const timeline = screen.getByRole('region', { name: 'Histórico completo' })
  expect(within(timeline).getByRole('alert')).toHaveTextContent(
    'Acompanhamento temporariamente indisponível.',
  )
  expect(within(timeline).getByText('Chamado recebido')).toBeInTheDocument()
})

test('shows a Portuguese state badge on every semantic timeline item', () => {
  const states = [
    ['completed', 'Concluído'],
    ['active', 'Em andamento'],
    ['waiting', 'Aguardando'],
    ['warning', 'Atenção'],
    ['failed', 'Falhou'],
  ] as const
  const events = states.map(([state], index) => ({
    ...event(index + 1),
    state,
    title: `Evento ${index + 1}`,
  }))

  render(<AgentDashboard ticket={waitingTicket} events={events} connection="active" />)

  const items = within(screen.getByRole('list', { name: 'Linha do tempo do agente' }))
    .getAllByRole('listitem')
  expect(items).toHaveLength(states.length)
  states.forEach(([, label], index) => {
    expect(within(items[index]).getByText(label)).toBeVisible()
  })
})

test('renders a separate decision focus from the highest event id', () => {
  const newest = {
    ...event(7),
    title: 'Evento mais recente',
    description: 'Esta é a decisão atual.',
    state: 'warning' as const,
  }

  render(
    <AgentDashboard
      ticket={waitingTicket}
      events={[newest, event(2), event(4)]}
      connection="active"
    />,
  )

  const focus = screen.getByRole('region', { name: 'Decisão em foco' })
  expect(within(focus).getByText('Evento mais recente', { selector: 'strong' }))
    .toBeInTheDocument()
  expect(within(focus).getByText('Esta é a decisão atual.')).toBeInTheDocument()
  expect(within(focus).getByText('Atenção')).toBeVisible()
  expect(focus.querySelector('time')).toHaveAttribute('datetime', newest.created_at)
  expect(within(screen.getByRole('list', { name: 'Linha do tempo do agente' }))
    .getAllByRole('listitem')).toHaveLength(3)
})

test('uses corrected ticket equipment and ignores empty event signals', () => {
  const latest = {
    ...event(4),
    metadata: {
      symptom: '',
      detected: true,
      model: 'OCR-ANTIGO',
      serial: '',
      outcome: 'checklist_enviado',
      priority: 'urgente',
      unsafe: ['não exibir'],
    },
  }
  render(<AgentDashboard ticket={waitingTicket} events={[event(1), latest]} connection="active" />)

  expect(screen.getByText('CX-400')).toBeInTheDocument()
  expect(screen.getByText('BR-DEMO-001')).toBeInTheDocument()
  expect(screen.getByText('congela_bebidas')).toBeInTheDocument()
  expect(screen.getByText('urgente')).toBeInTheDocument()
  expect(screen.queryByText('OCR-ANTIGO')).not.toBeInTheDocument()
  expect(screen.queryByText('não exibir')).not.toBeInTheDocument()
})
