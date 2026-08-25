import type { TicketEventCategory, TicketEventState } from '../../clients/client'

export const eventCategoryLabels: Record<TicketEventCategory, string> = {
  ticket_created: 'Chamado recebido',
  scope_validated: 'Escopo validado',
  risk_evaluated: 'Risco verificado',
  stage_changed: 'Etapa atualizada',
  agent_requested: 'Agente consultado',
  agent_interpreted: 'Resposta do agente interpretada',
  ocr_completed: 'Etiqueta processada',
  equipment_confirmed: 'Equipamento confirmado',
  triage_decision: 'Decisão de triagem',
  checklist_sent: 'Checklist enviado',
  confirmation_waiting: 'Confirmação aguardada',
  ticket_resolved: 'Chamado resolvido',
  supplier_routed: 'Chamado encaminhado ao fornecedor',
  confirmation_expired: 'Confirmação expirada',
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
