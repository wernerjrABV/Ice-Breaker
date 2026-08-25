import { afterEach, expect, test, vi } from 'vitest'
import { createTicket, expireConfirmations, getTicket, getTicketEvents, sendMessage, sendPhoto, sendSerial } from './client'
import type { Message, Ticket } from './client'

afterEach(() => vi.restoreAllMocks())

const normalBackendTicket: Ticket = {
  id: 'T-1',
  nome_pdv: 'Bar do João',
  assunto: 'Não gela',
  descricao_base: 'Baixa refrigeração',
  equipment_type: 'cooler',
  status: 'em_triagem',
  stage: 'aguardando_proximidade',
  confirmation_deadline: null,
  priority: 'normal',
  outcome_reason: '',
  equipment: null,
  messages: [],
  supplier_summary: null,
}

test('creates a ticket with the base call information', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ id: 'T-1' }), { status: 201 }),
  )

  await expect(createTicket('Bar do João', 'Não gela', 'Baixa refrigeração', 'cooler')).resolves.toEqual({ id: 'T-1' })
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/tickets'),
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({
        nome_pdv: 'Bar do João',
        assunto: 'Não gela',
        descricao_base: 'Baixa refrigeração',
        equipment_type: 'cooler',
      }),
    }),
  )
})

test('gets a ticket by id', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(normalBackendTicket), { status: 200 }),
  )

  await expect(getTicket('T-1')).resolves.toEqual(normalBackendTicket)
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/tickets/T-1'))
})

test('gets only ticket events after the supplied id', async () => {
  const payload = {
    items: [{
      id: 8,
      ticket_id: 'T-1',
      category: 'risk_evaluated',
      title: 'Risco verificado',
      description: 'Nenhum risco crítico detectado.',
      state: 'completed',
      metadata: { detected: false, risk_flags: [] },
      created_at: '2026-08-25T17:32:09Z',
    }],
    last_id: 8,
    terminal: false,
  }
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(payload), { status: 200 }),
  )

  await expect(getTicketEvents('T-1', 7, 100)).resolves.toEqual(payload)
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/tickets/T-1/events?after=7&limit=100'),
  )
})

test('sends a message to a ticket', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(normalBackendTicket), { status: 200 }),
  )

  await sendMessage('T-1', 'Ainda não gela')
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/tickets/T-1/messages'), expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ content: 'Ainda não gela' }),
  }))
})

test('sends equipment serial to a ticket', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(normalBackendTicket), { status: 200 }),
  )

  await sendSerial('T-1', 'CX-400', 'BR-1')
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/tickets/T-1/equipment/serial'), expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ modelo: 'CX-400', numero_serie: 'BR-1' }),
  }))
})

test('sends an equipment photo to a ticket', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(normalBackendTicket), { status: 200 }),
  )
  const photo = new File(['image'], 'label.jpg', { type: 'image/jpeg' })

  await sendPhoto('T-1', photo)
  const request = fetchMock.mock.calls[0]?.[1]
  expect(fetchMock).toHaveBeenCalledWith(
    'http://127.0.0.1:8001/tickets/T-1/equipment/photo',
    expect.any(Object),
  )
  expect(request?.method).toBe('POST')
  expect(request?.body).toBeInstanceOf(FormData)
  expect((request?.body as FormData).get('photo')).toBe(photo)
})

test('expires confirmation deadlines', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(['T-1']), { status: 200 }),
  )

  await expect(expireConfirmations()).resolves.toEqual(['T-1'])
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/maintenance/expire-confirmations'), expect.objectContaining({
    method: 'POST',
  }))
})

test('includes the HTTP status in Portuguese errors', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 503 }))

  await expect(getTicket('T-1')).rejects.toThrow('Não foi possível obter o ticket: 503')
})

test('wraps network failures with a Portuguese contextual error', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

  await expect(sendMessage('T-1', 'Ainda não gela')).rejects.toThrow(
    'Não foi possível enviar a mensagem: erro de rede',
  )
})

test('models backend messages without ids and with every emitted kind', () => {
  const kinds: Message['kind'][] = [
    'text',
    'opening',
    'conversation',
    'identification',
    'routing',
    'resolution',
    'checklist',
  ]
  const backendMessages: Message[] = kinds.map((kind) => ({
    role: 'assistant',
    content: 'Mensagem do backend',
    kind,
    created_at: '2026-08-21T00:00:00Z',
  }))

  expect(backendMessages).toHaveLength(kinds.length)
  expect(backendMessages.every((message) => !('id' in message))).toBe(true)
})

test('models the required backend priority and outcome reason fields', () => {
  const backendTicket: Ticket = {
    ...normalBackendTicket,
    id: 'T-URGENT',
    assunto: 'Cheiro de queimado',
    descricao_base: 'Odor forte no cooler',
    status: 'encaminhado_fornecedor',
    stage: 'finalizado',
    priority: 'urgente',
    outcome_reason: 'risco_critico',
    supplier_summary: {
      ticket_id: 'T-URGENT',
      nome_pdv: 'Bar do João',
      assunto: 'Cheiro de queimado',
      equipamento: null,
      evidencias: [
        { tipo: 'descricao_inicial', descricao: 'Odor forte no cooler' },
      ],
      acoes_tentadas: [],
      prioridade: 'urgente',
      motivo: 'Risco crítico identificado.',
    },
  }

  expect(backendTicket.priority).toBe('urgente')
  expect(backendTicket.outcome_reason).toBe('risco_critico')
  expect(backendTicket.supplier_summary?.equipamento).toBeNull()
  expect(backendTicket.supplier_summary?.evidencias[0]?.tipo).toBe('descricao_inicial')
})
