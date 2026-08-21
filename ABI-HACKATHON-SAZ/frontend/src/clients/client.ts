const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001'

export interface KickoffRequest {
  id: string
  status: string
  input: { subject?: string } | null
  result: string | null
  error: string | null
  created_at: string
  updated_at: string
}

export async function createKickoffRequest(subject: string): Promise<{ id: string }> {
  const response = await fetch(`${API_BASE_URL}/kickoff/async`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject }),
  })

  if (!response.ok) {
    throw new Error(`Não foi possível criar a solicitação: ${response.status}`)
  }

  return response.json()
}

export async function listKickoffRequests(): Promise<KickoffRequest[]> {
  const response = await fetch(`${API_BASE_URL}/kickoff/async`)

  if (!response.ok) {
    throw new Error(`Não foi possível listar as solicitações: ${response.status}`)
  }

  return response.json()
}
