import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode } from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Message, SupplierSummary, Ticket } from '../../clients/client'
import Home from './Home'

const client = vi.hoisted(() => ({
  createKickoffRequest: vi.fn(),
  createTicket: vi.fn(),
  expireConfirmations: vi.fn(),
  getTicket: vi.fn(),
  getTicketEvents: vi.fn(),
  listKickoffRequests: vi.fn(),
  sendMessage: vi.fn(),
  sendPhoto: vi.fn(),
  sendSerial: vi.fn(),
}))

vi.mock('../../clients/client', () => client)

const createdAt = '2026-08-21T12:00:00Z'
const confirmationDeadline = new Date(Date.now() + 30 * 60_000).toISOString()

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
    equipment_type: 'cooler',
    status: 'em_triagem',
    stage: 'aguardando_proximidade',
    confirmation_deadline: null,
    priority: 'normal',
    outcome_reason: '',
    equipment: null,
    supplier_summary: null,
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

function supplierSummary(
  overrides: Partial<SupplierSummary> = {},
): SupplierSummary {
  return {
    ticket_id: 'T-1',
    nome_pdv: 'Bar do João',
    assunto: 'Não gela',
    equipamento: {
      tipo: 'cooler',
      modelo: 'CX-400',
      numero_serie: 'BR-12345',
      confianca: 0.98,
      foto_etiqueta: 'etiqueta.jpg',
    },
    evidencias: [
      { tipo: 'descricao_inicial', descricao: 'Temperatura alta' },
      { tipo: 'relato_pdv', descricao: 'Não resolveu' },
      { tipo: 'foto_etiqueta', descricao: 'etiqueta.jpg' },
    ],
    acoes_tentadas: [
      'Confira se a ventilação externa está livre.',
      'Verifique se a porta fecha completamente.',
      'Verifique o ajuste de temperatura.',
      'Observe se há gelo visível bloqueando a circulação.',
    ],
    prioridade: 'normal',
    motivo: 'problema_persistiu_apos_checklist',
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

const equipmentConfirmationTicket = ticket({
  stage: 'aguardando_confirmacao_equipamento',
  equipment: {
    modelo: 'CX-400',
    numero_serie: 'BR-12345',
    confianca: 0.98,
    image_name: 'etiqueta.jpg',
  },
  outcome_reason: 'identificacao_aguardando_confirmacao',
  messages: [
    ...identificationTicket.messages,
    message(
      'assistant',
      'Confira o modelo e o número de série exibidos. Os dados estão corretos?',
      'identification',
    ),
  ],
})

const waitingTicket = ticket({
  status: 'aguardando_confirmacao',
  stage: 'aguardando_confirmacao',
  confirmation_deadline: confirmationDeadline,
  equipment: equipmentConfirmationTicket.equipment,
  messages: [
    ...equipmentConfirmationTicket.messages,
    message('user', 'Sim, dados corretos', 'text'),
    message(
      'assistant',
      'Siga estas verificações seguras: 1. Ajuste a temperatura. O cooler voltou a funcionar corretamente?',
      'checklist',
    ),
  ],
})

beforeEach(() => {
  vi.resetAllMocks()
  client.createTicket.mockResolvedValue({ id: 'T-1' })
  client.getTicketEvents.mockResolvedValue({ items: [], last_id: 0, terminal: false })
  client.listKickoffRequests.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

test('shows the live chat beside the agent dashboard for the same ticket', async () => {
  client.getTicket.mockResolvedValue(ticket())
  client.getTicketEvents.mockResolvedValue({
    items: [{
      id: 1,
      ticket_id: 'T-1',
      category: 'ticket_created',
      title: 'Chamado recebido',
      description: 'O CoolCare iniciou a triagem.',
      state: 'completed',
      metadata: { equipment_type: 'cooler' },
      created_at: createdAt,
    }],
    last_id: 1,
    terminal: false,
  })

  render(<Home />)

  const experience = await screen.findByLabelText('Experiência do chamado')
  expect(experience).toHaveClass('case-experience')
  expect(screen.getByLabelText('Atendimento CoolCare')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Inteligência do agente' })).toBeInTheDocument()
  expect(await screen.findByText('Chamado recebido')).toBeInTheDocument()
  expect(client.getTicketEvents).toHaveBeenCalledWith('T-1', 0, 100)
})

test('keeps the chat usable while agent-event polling reconnects', async () => {
  vi.useFakeTimers()
  client.getTicket.mockResolvedValue(ticket())
  client.getTicketEvents.mockRejectedValue(new Error('offline'))

  render(<Home />)
  await act(async () => undefined)

  expect(screen.getByText('Reconectando')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /^sim$/i })).toBeEnabled()
})

test('starts with the proactive message and asks for equipment identification', async () => {
  const user = userEvent.setup()
  const actionResponse = ticket({
    stage: 'aguardando_identificacao',
    messages: [message('assistant', 'Resposta transitória da ação.', 'conversation')],
  })
  client.getTicket
    .mockResolvedValueOnce(ticket())
    .mockResolvedValueOnce(identificationTicket)
  client.sendMessage.mockResolvedValue(actionResponse)

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
    'cooler',
  )
  expect(screen.queryByText('Resposta transitória da ação.')).not.toBeInTheDocument()
  expect(client.getTicket.mock.calls).toEqual([['T-1'], ['T-1']])
})

test('creates only one startup ticket when StrictMode replays the effect', async () => {
  client.getTicket.mockResolvedValue(ticket())

  render(<StrictMode><Home /></StrictMode>)

  await screen.findByText(/quero entender melhor/i)
  expect(client.createTicket).toHaveBeenCalledTimes(1)
  expect(client.getTicket.mock.calls).toEqual([['T-1']])
})

test('retries startup after a controlled create failure and recovers', async () => {
  const user = userEvent.setup()
  client.createTicket
    .mockRejectedValueOnce(new Error('Não foi possível criar o ticket: erro de rede'))
    .mockResolvedValueOnce({ id: 'T-1' })
  client.getTicket.mockResolvedValue(ticket())

  render(<Home />)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Não foi possível criar o ticket: erro de rede',
  )
  await user.click(screen.getByRole('button', { name: /tentar novamente/i }))

  expect(await screen.findByText(/quero entender melhor/i)).toBeInTheDocument()
  expect(client.createTicket).toHaveBeenCalledTimes(2)
  expect(client.getTicket.mock.calls).toEqual([['T-1']])
})

test('retries a startup refresh with the existing ticket id', async () => {
  const user = userEvent.setup()
  client.getTicket
    .mockRejectedValueOnce(new Error('Não foi possível obter o ticket: erro de rede'))
    .mockResolvedValueOnce(ticket())

  render(<Home />)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Não foi possível obter o ticket: erro de rede',
  )
  await user.click(screen.getByRole('button', { name: /tentar novamente/i }))

  expect(await screen.findByText(/quero entender melhor/i)).toBeInTheDocument()
  expect(client.createTicket).toHaveBeenCalledTimes(1)
  expect(client.getTicket.mock.calls).toEqual([['T-1'], ['T-1']])
})

test('keeps the message history flexible and the composer pinned after it', async () => {
  client.getTicket.mockResolvedValue(ticket())

  render(<Home />)

  const shell = await screen.findByLabelText('Atendimento CoolCare')
  const chat = within(screen.getByLabelText('Atendimento CoolCare')).getByRole('main')
  const composer = screen.getByRole('contentinfo')
  expect(shell).toHaveClass('phone-shell-flex')
  expect(chat).toHaveClass('chat-area-flexible')
  expect(composer).toHaveClass('composer-pinned')
  expect(chat.nextElementSibling).toBe(composer)
})

test('shows remote saving only after positive confirmation', async () => {
  const user = userEvent.setup()
  const resolvedTicket = ticket({
    status: 'resolvido_remotamente',
    stage: 'finalizado',
    outcome_reason: 'confirmacao_positiva_pdv',
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
  client.sendMessage.mockResolvedValue(waitingTicket)

  render(<Home />)

  expect(await screen.findByText(/aguardando confirmação/i)).toBeInTheDocument()
  expect(screen.getByText(/confirmação até/i)).toBeInTheDocument()
  expect(
    within(screen.getByLabelText('Atendimento CoolCare')).queryByText(/R\$ 200/),
  ).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /sim, resolveu/i }))

  expect(
    await screen.findByRole('heading', { name: /resolvido remotamente/i }),
  ).toBeInTheDocument()
  expect(within(screen.getByLabelText('Resultado do atendimento')).getByText(/R\$ 200/)).toBeInTheDocument()
  expect(client.getTicket.mock.calls).toEqual([['T-1'], ['T-1']])
})

test('retains the successful final-confirmation POST when the refresh fails', async () => {
  const user = userEvent.setup()
  const resolvedTicket = ticket({
    status: 'resolvido_remotamente',
    stage: 'finalizado',
    outcome_reason: 'confirmacao_positiva_pdv',
    equipment: waitingTicket.equipment,
    messages: [
      ...waitingTicket.messages,
      message('user', 'Sim, resolveu', 'text'),
      message('assistant', 'Chamado resolvido remotamente.', 'resolution'),
    ],
  })
  client.getTicket
    .mockResolvedValueOnce(waitingTicket)
    .mockRejectedValueOnce(new Error('Não foi possível obter o ticket: erro de rede'))
    .mockResolvedValueOnce(resolvedTicket)
  client.sendMessage.mockResolvedValue(resolvedTicket)

  render(<Home />)
  await screen.findByText(/aguardando confirmação/i)
  await user.click(screen.getByRole('button', { name: /sim, resolveu/i }))

  expect(
    await screen.findByRole('heading', { name: /resolvido remotamente/i }),
  ).toBeInTheDocument()
  expect(within(screen.getByLabelText('Resultado do atendimento')).getByText(/R\$ 200/)).toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent(/obter o ticket.*rede/i)

  await user.click(screen.getByRole('button', { name: /tentar atualizar/i }))
  expect(client.createTicket).toHaveBeenCalledTimes(1)
  expect(client.getTicket.mock.calls).toEqual([['T-1'], ['T-1'], ['T-1']])
})

test('shows supplier routing summary without remote saving', async () => {
  const user = userEvent.setup()
  const supplierTicket = ticket({
    status: 'encaminhado_fornecedor',
    stage: 'finalizado',
    outcome_reason: 'problema_persistiu_apos_checklist',
    equipment: waitingTicket.equipment,
    supplier_summary: supplierSummary(),
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
  client.sendMessage.mockResolvedValue(waitingTicket)

  render(<Home />)
  await screen.findByText(/aguardando confirmação/i)
  await user.click(screen.getByRole('button', { name: /^não$/i }))

  expect(
    await screen.findByRole('heading', { name: /encaminhado ao fornecedor/i }),
  ).toBeInTheDocument()
  const result = screen.getByLabelText('Resultado do atendimento')
  expect(within(result).getByText(/CX-400.*BR-12345/i)).toBeInTheDocument()
  expect(within(result).getByText('Confira se a ventilação externa está livre.')).toBeInTheDocument()
  expect(within(result).getByText('etiqueta.jpg')).toBeInTheDocument()
  expect(within(result).getByText('problema_persistiu_apos_checklist')).toBeInTheDocument()
  expect(screen.queryByText(/histórico, evidências.*seguem/i)).not.toBeInTheDocument()
  expect(
    within(screen.getByLabelText('Atendimento CoolCare')).queryByText(/R\$ 200/),
  ).not.toBeInTheDocument()
  expect(client.getTicket.mock.calls).toEqual([['T-1'], ['T-1']])
})

test.each([
  {
    priority: 'urgente' as const,
    routingMessage: 'O chamado foi encaminhado ao fornecedor.',
    expectedUrgent: true,
  },
  {
    priority: 'normal' as const,
    routingMessage: 'Não manipule o equipamento enquanto aguarda o fornecedor.',
    expectedUrgent: false,
  },
])('derives urgent presentation strictly from $priority priority', async ({
  priority,
  routingMessage,
  expectedUrgent,
}) => {
  const supplierTicket = ticket({
    status: 'encaminhado_fornecedor',
    stage: 'finalizado',
    priority,
    outcome_reason: priority === 'urgente' ? 'risco_critico' : 'atendimento_tecnico',
    supplier_summary: supplierSummary({
      prioridade: priority,
      motivo: priority === 'urgente' ? 'Risco crítico identificado.' : 'atendimento_tecnico',
    }),
    messages: [message('assistant', routingMessage, 'routing')],
  })
  client.getTicket.mockResolvedValue(supplierTicket)

  render(<Home />)
  await screen.findByRole('heading', { name: /encaminhado ao fornecedor/i })

  const urgentWarning = screen.queryByText(/aviso urgente/i)
  if (expectedUrgent) {
    expect(urgentWarning).toBeInTheDocument()
    expect(screen.getByLabelText('Resultado do atendimento')).toHaveClass('result-card-urgent')
  } else {
    expect(urgentWarning).not.toBeInTheDocument()
    expect(screen.getByLabelText('Resultado do atendimento')).not.toHaveClass('result-card-urgent')
  }
})

test('renders urgent supplier evidence when equipment is not yet identified', async () => {
  client.getTicket.mockResolvedValue(ticket({
    nome_pdv: 'Conveniência Estação',
    assunto: 'Cheiro a queimado',
    descricao_base: 'Odor forte vindo do cooler',
    status: 'encaminhado_fornecedor',
    stage: 'finalizado',
    priority: 'urgente',
    outcome_reason: 'Risco crítico identificado.',
    equipment: null,
    supplier_summary: supplierSummary({
      nome_pdv: 'Conveniência Estação',
      assunto: 'Cheiro a queimado',
      equipamento: null,
      evidencias: [
        { tipo: 'descricao_inicial', descricao: 'Odor forte vindo do cooler' },
      ],
      acoes_tentadas: [],
      prioridade: 'urgente',
      motivo: 'Risco crítico identificado.',
    }),
  }))

  render(<Home />)

  await screen.findByRole('heading', { name: /encaminhado ao fornecedor/i })
  const result = screen.getByLabelText('Resultado do atendimento')
  expect(within(result).getByText('Odor forte vindo do cooler')).toBeInTheDocument()
  expect(within(result).getByText('Risco crítico identificado.')).toBeInTheDocument()
  expect(within(result).getByText(/prioridade urgente/i)).toBeInTheDocument()
  expect(screen.queryByText(/histórico, evidências.*seguem/i)).not.toBeInTheDocument()
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

test('expires the deadline once, disables confirmation, and refreshes the supplier outcome', async () => {
  vi.useFakeTimers()
  vi.setSystemTime('2026-08-21T12:00:00Z')
  let completeExpiry: ((ticketIds: string[]) => void) | undefined
  const beforeExpiry = {
    ...waitingTicket,
    confirmation_deadline: '2026-08-21T12:00:30Z',
  }
  const afterExpiry = ticket({
    status: 'encaminhado_fornecedor',
    stage: 'finalizado',
    outcome_reason: 'sem_confirmacao_pdv',
    equipment: waitingTicket.equipment,
    supplier_summary: supplierSummary({ motivo: 'sem_confirmacao_pdv' }),
    messages: [
      ...waitingTicket.messages,
      message(
        'assistant',
        'Como não houve confirmação do PDV em 30 minutos, o chamado foi encaminhado ao fornecedor.',
        'routing',
      ),
    ],
  })
  client.getTicket
    .mockResolvedValueOnce(beforeExpiry)
    .mockResolvedValueOnce(afterExpiry)
  client.expireConfirmations.mockImplementation(
    () => new Promise<string[]>((resolve) => { completeExpiry = resolve }),
  )

  render(<Home />)
  await act(async () => undefined)
  expect(screen.getByRole('button', { name: /sim, resolveu/i })).toBeEnabled()

  act(() => vi.advanceTimersByTime(30_000))

  expect(client.expireConfirmations).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button', { name: /sim, resolveu/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /^não$/i })).toBeDisabled()
  expect(screen.queryByRole('heading', { name: /encaminhado ao fornecedor/i })).not.toBeInTheDocument()

  await act(async () => {
    completeExpiry?.(['T-1'])
  })

  expect(screen.getByRole('heading', { name: /encaminhado ao fornecedor/i })).toBeInTheDocument()
  expect(client.getTicket.mock.calls).toEqual([['T-1'], ['T-1']])
  act(() => vi.advanceTimersByTime(60_000))
  expect(client.expireConfirmations).toHaveBeenCalledTimes(1)
})

test('retries a no-op expiry with bounded backoff and no concurrent duplicate', async () => {
  vi.useFakeTimers()
  vi.setSystemTime('2026-08-21T12:00:00Z')
  const beforeExpiry = {
    ...waitingTicket,
    confirmation_deadline: '2026-08-21T12:00:01Z',
  }
  const afterExpiry = ticket({
    status: 'encaminhado_fornecedor',
    stage: 'finalizado',
    outcome_reason: 'sem_confirmacao_pdv',
    equipment: waitingTicket.equipment,
    supplier_summary: supplierSummary({ motivo: 'sem_confirmacao_pdv' }),
  })
  let finishFirstExpiry: ((ticketIds: string[]) => void) | undefined
  client.getTicket
    .mockResolvedValueOnce(beforeExpiry)
    .mockResolvedValueOnce(beforeExpiry)
    .mockResolvedValueOnce(afterExpiry)
  client.expireConfirmations
    .mockImplementationOnce(
      () => new Promise<string[]>((resolve) => { finishFirstExpiry = resolve }),
    )
    .mockResolvedValueOnce(['T-1'])

  render(<Home />)
  await act(async () => undefined)
  act(() => vi.advanceTimersByTime(1_000))
  expect(client.expireConfirmations).toHaveBeenCalledTimes(1)
  act(() => vi.advanceTimersByTime(30_000))
  expect(client.expireConfirmations).toHaveBeenCalledTimes(1)

  await act(async () => { finishFirstExpiry?.([]) })
  expect(screen.getByText(/prazo encerrado/i)).toBeInTheDocument()
  await act(async () => { vi.advanceTimersByTime(1_000) })

  expect(client.expireConfirmations).toHaveBeenCalledTimes(2)
  expect(
    screen.getByRole('heading', { name: /encaminhado ao fornecedor/i }),
  ).toBeInTheDocument()
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
    .mockResolvedValueOnce(equipmentConfirmationTicket)
    .mockResolvedValueOnce(waitingTicket)
  client.sendPhoto.mockResolvedValue(identificationTicket)
  client.sendSerial.mockResolvedValue(uncertainTicket)
  client.sendMessage.mockResolvedValue(equipmentConfirmationTicket)

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
  expect(
    await screen.findByRole('region', { name: /confirmação do equipamento/i }),
  ).toHaveTextContent('CX-400')
  expect(screen.getByText(/BR-12345/i)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /sim, dados corretos/i }))
  expect(await screen.findByText(/aguardando confirmação/i)).toBeInTheDocument()
  expect(client.getTicket.mock.calls).toEqual([
    ['T-1'],
    ['T-1'],
    ['T-1'],
    ['T-1'],
  ])
})

test('retains successful serial confirmation and retries only the existing ticket refresh', async () => {
  const user = userEvent.setup()
  const uncertainTicket = ticket({
    stage: 'aguardando_identificacao',
    equipment: {
      modelo: 'CX-ANTIGO',
      numero_serie: '',
      confianca: 0.20,
      image_name: 'foto-etiqueta.jpg',
    },
    outcome_reason: 'identificacao_manual_necessaria',
  })
  const correctedTicket = ticket({
    stage: 'aguardando_confirmacao_equipamento',
    equipment: {
      modelo: 'CX-400',
      numero_serie: 'BR-MANUAL',
      confianca: 1,
      image_name: 'foto-etiqueta.jpg',
    },
  })
  client.getTicket
    .mockResolvedValueOnce(uncertainTicket)
    .mockRejectedValueOnce(new Error('Não foi possível obter o ticket: 503'))
    .mockResolvedValueOnce(correctedTicket)
  client.sendSerial.mockResolvedValue(correctedTicket)

  render(<Home />)
  await screen.findByRole('form', { name: /serial manual/i })
  await user.clear(screen.getByLabelText(/^modelo$/i))
  await user.type(screen.getByLabelText(/^modelo$/i), 'CX-400')
  await user.type(screen.getByLabelText(/número de série/i), 'BR-MANUAL')
  await user.click(screen.getByRole('button', { name: /confirmar equipamento/i }))

  const confirmation = await screen.findByRole('region', {
    name: /confirmação do equipamento/i,
  })
  expect(confirmation).toHaveTextContent('BR-MANUAL')
  expect(confirmation).toHaveTextContent('foto-etiqueta.jpg')
  expect(await screen.findByRole('alert')).toHaveTextContent(/obter o ticket.*503/i)

  await user.click(screen.getByRole('button', { name: /tentar atualizar/i }))
  expect(client.createTicket).toHaveBeenCalledTimes(1)
  expect(client.getTicket.mock.calls).toEqual([['T-1'], ['T-1'], ['T-1']])
})

test('shows confident OCR data and requires explicit confirmation', async () => {
  const user = userEvent.setup()
  client.getTicket
    .mockResolvedValueOnce(identificationTicket)
    .mockResolvedValueOnce(equipmentConfirmationTicket)
    .mockResolvedValueOnce(waitingTicket)
  client.sendPhoto.mockResolvedValue(equipmentConfirmationTicket)
  client.sendMessage.mockResolvedValue(waitingTicket)

  render(<Home />)

  await user.upload(
    await screen.findByLabelText(/foto da etiqueta/i),
    new File(['image'], 'etiqueta.jpg', { type: 'image/jpeg' }),
  )
  const confirmation = await screen.findByRole('region', {
    name: /confirmação do equipamento/i,
  })
  expect(confirmation).toHaveTextContent('CX-400')
  expect(confirmation).toHaveTextContent('BR-12345')
  expect(screen.queryByText(/aguardando confirmação$/i)).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /sim, dados corretos/i }))

  expect(client.sendMessage).toHaveBeenCalledWith('T-1', 'Sim, dados corretos')
  expect(await screen.findByText(/aguardando confirmação/i)).toBeInTheDocument()
})

test('negative equipment confirmation reopens manual correction', async () => {
  const user = userEvent.setup()
  const correctionTicket = ticket({
    stage: 'aguardando_identificacao',
    outcome_reason: 'correcao_identificacao_necessaria',
    equipment: equipmentConfirmationTicket.equipment,
    messages: [
      ...equipmentConfirmationTicket.messages,
      message('user', 'Não, corrigir', 'text'),
      message(
        'assistant',
        'Certo. Corrija o modelo e o número de série antes de continuar.',
        'identification',
      ),
    ],
  })
  client.getTicket
    .mockResolvedValueOnce(equipmentConfirmationTicket)
    .mockResolvedValueOnce(correctionTicket)
  client.sendMessage.mockResolvedValue(correctionTicket)

  render(<Home />)
  await screen.findByRole('region', { name: /confirmação do equipamento/i })

  await user.click(screen.getByRole('button', { name: /não, corrigir/i }))

  expect(client.sendMessage).toHaveBeenCalledWith('T-1', 'Não, corrigir')
  expect(await screen.findByRole('form', { name: /serial manual/i })).toBeInTheDocument()
  expect(screen.getByLabelText(/^modelo$/i)).toHaveValue('CX-400')
  expect(screen.getByLabelText(/número de série/i)).toHaveValue('BR-12345')
})

test('disables conversation controls while a request is in progress', async () => {
  const user = userEvent.setup()
  let completeRequest: ((value: Ticket) => void) | undefined
  const actionResponse = ticket({
    stage: 'aguardando_identificacao',
    messages: [message('assistant', 'Resposta transitória da ação.', 'conversation')],
  })
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
    completeRequest?.(actionResponse)
  })
  await waitFor(() => expect(textBox).toBeEnabled())
  expect(screen.queryByText('Resposta transitória da ação.')).not.toBeInTheDocument()
  expect(client.getTicket.mock.calls).toEqual([['T-1'], ['T-1']])
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
