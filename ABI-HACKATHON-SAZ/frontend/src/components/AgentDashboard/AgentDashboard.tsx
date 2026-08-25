import type { Ticket, TicketEvent } from '../../clients/client'
import type { EventConnection } from '../../hooks/useTicketEvents'
import { AgentMetrics } from './AgentMetrics'
import { DecisionFocus } from './DecisionFocus'
import { DecisionSignals } from './DecisionSignals'
import { DecisionTimeline } from './DecisionTimeline'
import './AgentDashboard.css'

const connectionLabel: Record<EventConnection, string> = {
  idle: 'Preparando',
  loading: 'Preparando',
  active: 'Agente ativo',
  reconnecting: 'Reconectando',
  complete: 'Atendimento concluído',
}

export function AgentDashboard({
  ticket,
  events,
  connection,
}: {
  ticket: Ticket
  events: TicketEvent[]
  connection: EventConnection
}) {
  return (
    <aside className="agent-dashboard" role="region" aria-label="Inteligência do agente">
      <header className="agent-dashboard-header">
        <div><strong>CoolCare Intelligence</strong><span>{ticket.id}</span></div>
        <span className={`connection connection-${connection}`}><span aria-hidden="true" />{connectionLabel[connection]}</span>
      </header>
      <AgentMetrics ticket={ticket} />
      {events.length === 0 ? (
        <p className="agent-empty">Preparando acompanhamento do agente...</p>
      ) : (
        <>
          <DecisionFocus events={events} />
          <div className="agent-dashboard-grid">
            <DecisionTimeline events={events} />
            <DecisionSignals ticket={ticket} events={events} />
          </div>
        </>
      )}
    </aside>
  )
}
