import type { TicketEvent } from '../../clients/client'

function formatEventTime(createdAt: string): string {
  const timestamp = new Date(createdAt)
  if (Number.isNaN(timestamp.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(timestamp)
}

export function DecisionTimeline({ events }: { events: TicketEvent[] }) {
  const chronologicalEvents = [...events].sort((left, right) => left.id - right.id)

  return (
    <section className="agent-panel agent-timeline-panel" aria-labelledby="decision-timeline-title">
      <div className="agent-panel-heading">
        <p>Foco da decisão</p>
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
              <p>{item.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
