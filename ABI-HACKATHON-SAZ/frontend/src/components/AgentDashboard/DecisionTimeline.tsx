import type { TicketEvent } from '../../clients/client'
import { eventStateLabels, formatEventTime } from './eventPresentation'

export function DecisionTimeline({ events }: { events: TicketEvent[] }) {
  const chronologicalEvents = [...events].sort((left, right) => left.id - right.id)

  return (
    <section className="agent-panel agent-timeline-panel" aria-labelledby="decision-timeline-title">
      <div className="agent-panel-heading">
        <p>Histórico completo</p>
        <h2 id="decision-timeline-title">Linha do tempo</h2>
      </div>
      <ol className="agent-timeline" aria-label="Linha do tempo do agente">
        {chronologicalEvents.map((item) => (
          <li key={item.id} className={`agent-timeline-item agent-event-${item.state}`}>
            <span className="agent-event-dot" aria-hidden="true" />
            <div>
              <div className="agent-event-title-row">
                <strong>{item.title}</strong>
                <time dateTime={item.created_at}>{formatEventTime(item.created_at)}</time>
              </div>
              <span className={`agent-event-state agent-event-state-${item.state}`}>
                {eventStateLabels[item.state]}
              </span>
              <p>{item.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
