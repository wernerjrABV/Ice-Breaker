import type { TicketEventState } from '../../clients/client'

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
