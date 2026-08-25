import type { Ticket, TicketStatus } from '../../clients/client'

export interface SavingPresentation {
  label: string
  value: string
  note: string
  tone: 'potential' | 'realized' | 'lost'
}

const stageProgress = {
  aguardando_proximidade: '1/5',
  aguardando_identificacao: '2/5',
  aguardando_confirmacao_equipamento: '2/5',
  diagnostico: '3/5',
  aguardando_confirmacao: '4/5',
  finalizado: '5/5',
} as const

// eslint-disable-next-line react-refresh/only-export-components -- exported for direct status-rule tests.
export function savingPresentation(status: TicketStatus): SavingPresentation {
  if (status === 'resolvido_remotamente') {
    return { label: 'Economia realizada', value: 'R$ 200', note: 'Visita técnica evitada', tone: 'realized' }
  }
  if (status === 'encaminhado_fornecedor') {
    return { label: 'Economia não realizada', value: 'R$ 0', note: 'Atendimento encaminhado', tone: 'lost' }
  }
  return { label: 'Economia potencial', value: 'R$ 200', note: 'Ainda não contabilizada', tone: 'potential' }
}

export function AgentMetrics({ ticket }: { ticket: Ticket }) {
  const saving = savingPresentation(ticket.status)
  const confidence = ticket.equipment ? `${Math.round(ticket.equipment.confianca * 100)}%` : '—'
  const priority = ticket.priority === 'urgente' ? 'Urgente' : 'Normal'

  return (
    <section className="agent-metrics" aria-label="Métricas do atendimento">
      <article className="agent-metric-card">
        <span>Etapa da conversa</span>
        <strong>{stageProgress[ticket.stage]}</strong>
      </article>
      <article className="agent-metric-card">
        <span>Confiança OCR</span>
        <strong>{confidence}</strong>
      </article>
      <article className="agent-metric-card">
        <span>Prioridade</span>
        <strong>{priority}</strong>
      </article>
      <article className={`agent-metric-card agent-saving agent-saving-${saving.tone}`}>
        <span>{saving.label}</span>
        <strong>{saving.value}</strong>
        <small>{saving.note}</small>
      </article>
    </section>
  )
}
