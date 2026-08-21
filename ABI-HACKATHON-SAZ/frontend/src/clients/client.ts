const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001'

export type TicketStatus =
  | 'em_triagem'
  | 'aguardando_confirmacao'
  | 'resolvido_remotamente'
  | 'encaminhado_fornecedor'

export interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  kind: 'text' | 'opening' | 'conversation' | 'identification' | 'routing' | 'resolution' | 'checklist'
  created_at: string
}

export interface Equipment {
  modelo: string
  numero_serie: string
  confianca: number
  image_name: string | null
}

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

export interface KickoffRequest {
  id: string
  status: string
  input: { subject?: string } | null
  result: string | null
  error: string | null
  created_at: string
  updated_at: string
}

async function readResponse<T>(response: Response, action: string): Promise<T> {
  if (!response.ok) {
    throw new Error(`${action}: ${response.status}`)
  }

  return response.json() as Promise<T>
}

async function request(input: RequestInfo | URL, init: RequestInit | undefined, action: string): Promise<Response> {
  try {
    return init === undefined ? await fetch(input) : await fetch(input, init)
  } catch {
    throw new Error(`${action}: erro de rede`)
  }
}

export async function createTicket(nomePdv: string, assunto: string, descricaoBase: string): Promise<{ id: string }> {
  const response = await request(`${API_BASE_URL}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nome_pdv: nomePdv, assunto, descricao_base: descricaoBase }),
  }, 'Não foi possível criar o ticket')

  return readResponse(response, 'Não foi possível criar o ticket')
}

export async function getTicket(ticketId: string): Promise<Ticket> {
  const response = await request(`${API_BASE_URL}/tickets/${ticketId}`, undefined, 'Não foi possível obter o ticket')

  return readResponse(response, 'Não foi possível obter o ticket')
}

export async function sendMessage(ticketId: string, content: string): Promise<Ticket> {
  const response = await request(`${API_BASE_URL}/tickets/${ticketId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  }, 'Não foi possível enviar a mensagem')

  return readResponse(response, 'Não foi possível enviar a mensagem')
}

export async function sendSerial(ticketId: string, modelo: string, numeroSerie: string): Promise<Ticket> {
  const response = await request(`${API_BASE_URL}/tickets/${ticketId}/equipment/serial`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ modelo, numero_serie: numeroSerie }),
  }, 'Não foi possível enviar o serial')

  return readResponse(response, 'Não foi possível enviar o serial')
}

export async function sendPhoto(ticketId: string, photo: File): Promise<Ticket> {
  const formData = new FormData()
  formData.append('photo', photo)
  const response = await request(`${API_BASE_URL}/tickets/${ticketId}/equipment/photo`, {
    method: 'POST',
    body: formData,
  }, 'Não foi possível enviar a foto')

  return readResponse(response, 'Não foi possível enviar a foto')
}

export async function expireConfirmations(): Promise<string[]> {
  const response = await request(`${API_BASE_URL}/maintenance/expire-confirmations`, {
    method: 'POST',
  }, 'Não foi possível expirar as confirmações')

  return readResponse(response, 'Não foi possível expirar as confirmações')
}

export async function createKickoffRequest(subject: string): Promise<{ id: string }> {
  const response = await request(`${API_BASE_URL}/kickoff/async`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject }),
  }, 'Não foi possível criar a solicitação')

  return readResponse(response, 'Não foi possível criar a solicitação')
}

export async function listKickoffRequests(): Promise<KickoffRequest[]> {
  const response = await request(`${API_BASE_URL}/kickoff/async`, undefined, 'Não foi possível listar as solicitações')

  return readResponse(response, 'Não foi possível listar as solicitações')
}
