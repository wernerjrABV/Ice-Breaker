import type { TicketEventCategory, TicketEventState } from '../../clients/client'

export const eventCategoryLabels: Partial<Record<TicketEventCategory, string>> = {
  initial_triage_started: 'Triagem inicial iniciada',
  initial_triage_routed_supplier: 'Encaminhamento inicial ao fornecedor',
  pdv_conversation_started: 'Conversa com o PDV iniciada',
  remote_solution_found: 'Solução remota encontrada',
}

export const eventStateLabels: Record<TicketEventState, string> = {
  completed: 'Concluído',
  active: 'Em andamento',
  waiting: 'Aguardando',
  warning: 'Atenção',
  failed: 'Falhou',
}

export function formatEventTime(createdAt: string): string {
  const timestamp = new Date(createdAt)
  if (Number.isNaN(timestamp.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(timestamp)
}
