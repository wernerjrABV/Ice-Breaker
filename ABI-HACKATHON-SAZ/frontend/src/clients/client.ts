const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001'

export type TicketStatus =
  | 'em_triagem'
  | 'aguardando_confirmacao'
  | 'resolvido_remotamente'
  | 'encaminhado_fornecedor'

export type TicketPriority = 'normal' | 'urgente'
export type EquipmentType = 'cooler' | 'geladeira'
export type ConversationStage =
  | 'aguardando_proximidade'
  | 'aguardando_identificacao'
  | 'aguardando_confirmacao_equipamento'
  | 'diagnostico'
  | 'aguardando_confirmacao'
  | 'finalizado'

export interface Message {
  id?: number
  role: 'user' | 'assistant' | 'internal'
  content: string
  kind: 'text' | 'opening' | 'conversation' | 'identification' | 'routing' | 'resolution' | 'checklist' | 'internal_status'
  created_at: string
}

export interface Equipment {
  modelo: string
  numero_serie: string
  confianca: number
  image_name: string | null
}

export type SupplierEvidenceType =
  | 'descricao_inicial'
  | 'relato_pdv'
  | 'foto_etiqueta'

export interface SupplierEvidence {
  tipo: SupplierEvidenceType
  descricao: string
}

export interface SupplierEquipment {
  tipo: EquipmentType
  modelo: string
  numero_serie: string
  confianca: number
  foto_etiqueta: string | null
}

export interface SupplierSummary {
  ticket_id: string
  nome_pdv: string
  assunto: string
  equipamento: SupplierEquipment | null
  evidencias: SupplierEvidence[]
  acoes_tentadas: string[]
  prioridade: TicketPriority
  motivo: string
}

export interface Ticket {
  id: string
  nome_pdv: string
  assunto: string
  descricao_base: string
  equipment_type: EquipmentType
  status: TicketStatus
  stage: ConversationStage
  confirmation_deadline: string | null
  priority: TicketPriority
  outcome_reason: string
  equipment: Equipment | null
  messages: Message[]
  supplier_summary: SupplierSummary | null
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

export type TicketEventCategory =
  | 'ticket_created' | 'scope_validated' | 'risk_evaluated' | 'stage_changed'
  | 'agent_requested' | 'agent_interpreted' | 'ocr_completed'
  | 'equipment_confirmed' | 'triage_decision' | 'checklist_sent'
  | 'confirmation_waiting' | 'ticket_resolved' | 'supplier_routed'
  | 'confirmation_expired'

export type TicketEventState = 'completed' | 'active' | 'waiting' | 'warning' | 'failed'
export type TicketEventMetadataValue = string | number | boolean | null | string[]

export interface TicketEvent {
  id: number
  ticket_id: string
  category: TicketEventCategory
  title: string
  description: string
  state: TicketEventState
  metadata: Record<string, TicketEventMetadataValue>
  created_at: string
}

export interface TicketEventsResponse {
  items: TicketEvent[]
  last_id: number
  terminal: boolean
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

export async function createTicket(
  nomePdv: string,
  assunto: string,
  descricaoBase: string,
  equipmentType: EquipmentType = 'cooler',
): Promise<{ id: string }> {
  const response = await request(`${API_BASE_URL}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nome_pdv: nomePdv,
      assunto,
      descricao_base: descricaoBase,
      equipment_type: equipmentType,
    }),
  }, 'Não foi possível criar o ticket')

  return readResponse(response, 'Não foi possível criar o ticket')
}

export async function createDemoTicket(assunto: string): Promise<{ id: string }> {
  const response = await request(`${API_BASE_URL}/demo/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assunto }),
  }, 'Não foi possível criar o ticket')

  return readResponse(response, 'Não foi possível criar o ticket')
}

export async function getTicket(ticketId: string): Promise<Ticket> {
  const response = await request(`${API_BASE_URL}/tickets/${ticketId}`, undefined, 'Não foi possível obter o ticket')

  return readResponse(response, 'Não foi possível obter o ticket')
}

export async function getTicketEvents(
  ticketId: string,
  after = 0,
  limit = 100,
): Promise<TicketEventsResponse> {
  const params = new URLSearchParams({ after: String(after), limit: String(limit) })
  const response = await request(
    `${API_BASE_URL}/tickets/${ticketId}/events?${params}`,
    undefined,
    'Não foi possível acompanhar o agente',
  )
  return readResponse(response, 'Não foi possível acompanhar o agente')
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
