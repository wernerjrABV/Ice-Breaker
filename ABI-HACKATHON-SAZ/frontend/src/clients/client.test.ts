import { afterEach, expect, test, vi } from 'vitest'
import { createTicket, expireConfirmations, getTicket, sendMessage, sendPhoto, sendSerial } from './client'
import type { Message } from './client'

afterEach(() => vi.restoreAllMocks())

test('creates a ticket with the base call information', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ id: 'T-1' }), { status: 201 }),
  )

  await expect(createTicket('Bar do João', 'Não gela', 'Baixa refrigeração')).resolves.toEqual({ id: 'T-1' })
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/tickets'),
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ nome_pdv: 'Bar do João', assunto: 'Não gela', descricao_base: 'Baixa refrigeração' }),
    }),
  )
})

test('gets a ticket by id', async () => {
  const ticket = { id: 'T-1', messages: [] }
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(ticket), { status: 200 }),
  )

  await expect(getTicket('T-1')).resolves.toEqual(ticket)
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/tickets/T-1'))
})

test('sends a message to a ticket', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ id: 'T-1' }), { status: 200 }),
  )

  await sendMessage('T-1', 'Ainda não gela')
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/tickets/T-1/messages'), expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ content: 'Ainda não gela' }),
  }))
})

test('sends equipment serial to a ticket', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ id: 'T-1' }), { status: 200 }),
  )

  await sendSerial('T-1', 'CX-400', 'BR-1')
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/tickets/T-1/equipment/serial'), expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ modelo: 'CX-400', numero_serie: 'BR-1' }),
  }))
})

test('sends an equipment photo to a ticket', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ id: 'T-1' }), { status: 200 }),
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
