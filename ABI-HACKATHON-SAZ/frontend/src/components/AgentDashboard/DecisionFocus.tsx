import type { TicketEvent } from '../../clients/client'
import { eventStateLabels, formatEventTime } from './eventPresentation'

export function DecisionFocus({ events }: { events: TicketEvent[] }) {
  const newest = events.reduce((latest, item) => (
    item.id > latest.id ? item : latest
  ))

  return (
    <section className="agent-panel agent-focus-panel" aria-labelledby="decision-focus-title">
      <div className="agent-panel-heading">
        <p>Evento mais recente</p>
        <h2 id="decision-focus-title">Decisão em foco</h2>
      </div>
      <article className={`agent-focus-event agent-event-${newest.state}`}>
        <div className="agent-focus-title-row">
          <strong>{newest.title}</strong>
          <span className={`agent-event-state agent-event-state-${newest.state}`}>
            {eventStateLabels[newest.state]}
          </span>
        </div>
        <p>{newest.description}</p>
        <time dateTime={newest.created_at}>{formatEventTime(newest.created_at)}</time>
      </article>
    </section>
  )
}
