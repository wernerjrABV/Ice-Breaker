import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Message, Ticket } from '../../clients/client'
import Home from './Home'

const client = vi.hoisted(() => ({
  createKickoffRequest: vi.fn(),
  createTicket: vi.fn(),
  getTicket: vi.fn(),
  listKickoffRequests: vi.fn(),
  sendMessage: vi.fn(),
  sendPhoto: vi.fn(),
  sendSerial: vi.fn(),
}))

vi.mock('../../clients/client', () => client)

const createdAt = '2026-08-21T12:00:00Z'

function message(
  role: Message['role'],
  content: string,
  kind: Message['kind'],
): Message {
  return { role, content, kind, created_at: createdAt }
}

function ticket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    id: 'T-1',
    nome_pdv: 'Bar do João',
    assunto: 'Congela bebidas',
    descricao_base: 'Bebidas congelando',
    status: 'em_triagem',
    stage: 'aguardando_proximidade',
    confirmation_deadline: null,
    equipment: null,
    messages: [
      message(
        'assistant',
        'Olá! Recebi um chamado do Bar do João sobre Congela bebidas. Quero entender melhor o que está acontecendo e verificar se já consigo ajudar você agora. Você está próximo ao equipamento?',
        'opening',
      ),
    ],
    ...overrides,
  }
}

const identificationTicket = ticket({
  stage: 'aguardando_identificacao',
  messages: [
    ...ticket().messages,
    message('user', 'Sim', 'text'),
    message(
      'assistant',
      'Envie uma foto da etiqueta do cooler ou informe o modelo e o número de série.',
      'identification',
    ),
  ],
})

const waitingTicket = ticket({
  status: 'aguardando_confirmacao',
  stage: 'aguardando_confirmacao',
  confirmation_deadline: '2099-08-21T12:30:00Z',
  equipment: {
    modelo: 'CX-400',
    numero_serie: 'BR-12345',
    confianca: 0.98,
    image_name: 'etiqueta.jpg',
  },
  messages: [
    ...identificationTicket.messages,
    message(
      'assistant',
      'Siga estas verificações seguras: 1. Ajuste a temperatura. O cooler voltou a funcionar corretamente?',
      'checklist',
    ),
  ],
})

beforeEach(() => {
  vi.clearAllMocks()
  client.createTicket.mockResolvedValue({ id: 'T-1' })
  client.listKickoffRequests.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

test('starts with the proactive message and asks for equipment identification', async () => {
  const user = userEvent.setup()
  client.getTicket
    .mockResolvedValueOnce(ticket())
    .mockResolvedValueOnce(identificationTicket)
  client.sendMessage.mockResolvedValue(identificationTicket)

  render(<Home />)

  expect(
    await screen.findByText(/quero entender melhor.*ajudar você agora/i),
  ).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /^sim$/i }))

  expect(
    await screen.findByText(/foto da etiqueta.*número de série/i),
  ).toBeInTheDocument()
  expect(client.createTicket).toHaveBeenCalledWith(
    'Bar do João',
    'Congela bebidas',
    'Bebidas congelando',
  )
})

test('shows remote saving only after positive confirmation', async () => {
  const user = userEvent.setup()
  const resolvedTicket = ticket({
    status: 'resolvido_remotamente',
    stage: 'finalizado',
    equipment: waitingTicket.equipment,
    messages: [
      ...waitingTicket.messages,
      message('user', 'Sim, resolveu', 'text'),
      message(
        'assistant',
        'Ótimo! Registrei sua confirmação e encerrei o chamado como resolvido remotamente.',
        'resolution',
      ),
    ],
  })
  client.getTicket
    .mockResolvedValueOnce(waitingTicket)
    .mockResolvedValueOnce(resolvedTicket)
  client.sendMessage.mockResolvedValue(resolvedTicket)

  render(<Home />)

  expect(await screen.findByText(/aguardando confirmação/i)).toBeInTheDocument()
  expect(screen.getByText(/confirmação até/i)).toBeInTheDocument()
  expect(screen.queryByText(/R\$ 200/)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /sim, resolveu/i }))

  expect(
    await screen.findByRole('heading', { name: /resolvido remotamente/i }),
  ).toBeInTheDocument()
  expect(screen.getByText(/R\$ 200/)).toBeInTheDocument()
})

test('shows supplier routing summary without remote saving', async () => {
  const user = userEvent.setup()
  const supplierTicket = ticket({
    status: 'encaminhado_fornecedor',
    stage: 'finalizado',
    equipment: waitingTicket.equipment,
    messages: [
      ...waitingTicket.messages,
      message('user', 'Não', 'text'),
      message(
        'assistant',
        'Como o problema continua, encaminhei o chamado ao fornecedor.',
        'routing',
      ),
    ],
  })
  client.getTicket
    .mockResolvedValueOnce(waitingTicket)
    .mockResolvedValueOnce(supplierTicket)
  client.sendMessage.mockResolvedValue(supplierTicket)

  render(<Home />)
  await screen.findByText(/aguardando confirmação/i)
  await user.click(screen.getByRole('button', { name: /^não$/i }))

  expect(
    await screen.findByRole('heading', { name: /encaminhado ao fornecedor/i }),
  ).toBeInTheDocument()
  expect(screen.getByText(/CX-400.*BR-12345/i)).toBeInTheDocument()
  expect(screen.queryByText(/R\$ 200/)).not.toBeInTheDocument()
})

test('updates the visual confirmation countdown while waiting', async () => {
  vi.useFakeTimers()
  vi.setSystemTime('2026-08-21T12:00:00Z')
  client.getTicket.mockResolvedValue({
    ...waitingTicket,
    confirmation_deadline: '2026-08-21T12:30:00Z',
  })

  render(<Home />)
  await act(async () => undefined)
  expect(screen.getByText(/restam 30 min/i)).toBeInTheDocument()

  act(() => vi.advanceTimersByTime(60_000))

  expect(screen.getByText(/restam 29 min/i)).toBeInTheDocument()
})

test('offers manual serial after a photo has OCR confidence below 0.80', async () => {
  const user = userEvent.setup()
  const uncertainTicket = ticket({
    stage: 'aguardando_identificacao',
    equipment: {
      modelo: 'CX-400',
      numero_serie: 'BR-INCERTO',
      confianca: 0.79,
      image_name: 'etiqueta.jpg',
    },
    messages: [
      ...identificationTicket.messages,
      message(
        'assistant',
        'Não consegui confirmar a etiqueta com segurança. Informe o serial manualmente.',
        'identification',
      ),
    ],
  })
  client.getTicket
    .mockResolvedValueOnce(identificationTicket)
    .mockResolvedValueOnce(uncertainTicket)
    .mockResolvedValueOnce(waitingTicket)
  client.sendPhoto.mockResolvedValue(uncertainTicket)
  client.sendSerial.mockResolvedValue(waitingTicket)

  render(<Home />)

  const photoInput = await screen.findByLabelText(/foto da etiqueta/i)
  expect(photoInput).toHaveAttribute('accept', 'image/*')
  expect(photoInput).toHaveAttribute('capture', 'environment')
  await user.upload(
    photoInput,
    new File(['image'], 'etiqueta.jpg', { type: 'image/jpeg' }),
  )

  expect(await screen.findByRole('form', { name: /serial manual/i })).toBeInTheDocument()
  await user.clear(screen.getByLabelText(/^modelo$/i))
  await user.type(screen.getByLabelText(/^modelo$/i), 'CX-400')
  await user.clear(screen.getByLabelText(/número de série/i))
  await user.type(screen.getByLabelText(/número de série/i), 'BR-12345')
  await user.click(screen.getByRole('button', { name: /confirmar equipamento/i }))

  await waitFor(() => {
    expect(client.sendSerial).toHaveBeenCalledWith('T-1', 'CX-400', 'BR-12345')
  })
})

test('disables conversation controls while a request is in progress', async () => {
  const user = userEvent.setup()
  let completeRequest: ((value: Ticket) => void) | undefined
  client.getTicket
    .mockResolvedValueOnce(identificationTicket)
    .mockResolvedValueOnce(identificationTicket)
  client.sendMessage.mockImplementation(
    () => new Promise<Ticket>((resolve) => { completeRequest = resolve }),
  )

  render(<Home />)
  const textBox = await screen.findByRole('textbox', { name: /mensagem/i })
  await user.type(textBox, 'A porta ainda não fecha')
  await user.click(screen.getByRole('button', { name: /^enviar$/i }))

  expect(textBox).toBeDisabled()
  expect(screen.getByRole('button', { name: /enviando/i })).toBeDisabled()
  expect(screen.getByLabelText(/foto da etiqueta/i)).toBeDisabled()

  await act(async () => {
    completeRequest?.(identificationTicket)
  })
  await waitFor(() => expect(textBox).toBeEnabled())
})

test('shows controlled Portuguese errors and restores the controls', async () => {
  const user = userEvent.setup()
  client.getTicket.mockResolvedValue(ticket())
  client.sendMessage.mockRejectedValue(
    new Error('Não foi possível enviar a mensagem: erro de rede'),
  )

  render(<Home />)
  await screen.findByText(/quero entender melhor/i)
  await user.click(screen.getByRole('button', { name: /^sim$/i }))

  expect(
    await screen.findByRole('alert'),
  ).toHaveTextContent('Não foi possível enviar a mensagem: erro de rede')
  expect(screen.getByRole('button', { name: /^sim$/i })).toBeEnabled()
})
