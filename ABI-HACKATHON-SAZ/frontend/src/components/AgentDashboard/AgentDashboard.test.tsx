import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import type { Ticket, TicketEvent } from '../../clients/client'
import { AgentDashboard } from './AgentDashboard'
import { savingPresentation } from './AgentMetrics'

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

test('renders decision focus, safe signals, and chronological events', () => {
  render(<AgentDashboard ticket={waitingTicket} events={[event(2), event(1)]} connection="active" />)

  expect(screen.getByRole('region', { name: 'Intelig\u00eancia do agente' })).toBeInTheDocument()
  expect(screen.getByText('Agente ativo')).toBeInTheDocument()
  expect(screen.getByRole('list', { name: 'Linha do tempo do agente' })).toHaveTextContent('Chamado recebido')
  expect(screen.getByText('congela_bebidas')).toBeInTheDocument()
  expect(screen.getByText('R$ 200')).toBeInTheDocument()
})

test('keeps known event copy for an unknown future category', () => {
  const future = { ...event(3), category: 'future_event' as TicketEvent['category'], title: 'Nova etapa', description: 'Evento compat\u00edvel.' }
  render(<AgentDashboard ticket={waitingTicket} events={[future]} connection="active" />)

  expect(screen.getByText('Nova etapa')).toBeInTheDocument()
  expect(screen.getByText('Evento compat\u00edvel.')).toBeInTheDocument()
})

test('shows reconnecting without removing the last events', () => {
  render(<AgentDashboard ticket={waitingTicket} events={[event(1)]} connection="reconnecting" />)
  expect(screen.getByText('Reconectando')).toBeInTheDocument()
  expect(screen.getByText('Chamado recebido')).toBeInTheDocument()
})

test('uses newest safe event values before ticket fallbacks', () => {
  const latest = {
    ...event(4),
    metadata: {
      detected: true,
      model: 'CX-900',
      serial: 42,
      outcome: 'checklist_enviado',
      priority: 'urgente',
      unsafe: ['não exibir'],
    },
  }
  render(<AgentDashboard ticket={waitingTicket} events={[event(1), latest]} connection="active" />)

  expect(screen.getByText('CX-900')).toBeInTheDocument()
  expect(screen.getByText('42')).toBeInTheDocument()
  expect(screen.getByText('urgente')).toBeInTheDocument()
  expect(screen.queryByText('BR-DEMO-001')).not.toBeInTheDocument()
  expect(screen.queryByText('não exibir')).not.toBeInTheDocument()
})
