import type { Ticket, TicketEvent, TicketEventMetadataValue } from '../../clients/client'

type SignalKey = 'symptom' | 'detected' | 'model' | 'serial' | 'outcome' | 'priority'

const signalLabels: Record<SignalKey, string> = {
  symptom: 'Sintoma',
  detected: 'Detecção',
  model: 'Modelo',
  serial: 'Serial',
  outcome: 'Desfecho',
  priority: 'Prioridade',
}

function safeSignal(value: TicketEventMetadataValue | undefined): string | undefined {
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
    ? String(value)
    : undefined
}

function decisionSignals(ticket: Ticket, events: TicketEvent[]): Partial<Record<SignalKey, string>> {
  const signals: Partial<Record<SignalKey, string>> = {}
  const keys: SignalKey[] = ['symptom', 'detected', 'model', 'serial', 'outcome', 'priority']

  for (const item of [...events].sort((left, right) => right.id - left.id)) {
    for (const key of keys) {
      if (signals[key] !== undefined) continue
      const value = safeSignal(item.metadata[key])
      if (value !== undefined) signals[key] = value
    }
  }
  signals.model ??= ticket.equipment?.modelo
  signals.serial ??= ticket.equipment?.numero_serie
  signals.outcome ??= ticket.outcome_reason
  signals.priority ??= ticket.priority
  return signals
}

export function DecisionSignals({ ticket, events }: { ticket: Ticket; events: TicketEvent[] }) {
  const signals = decisionSignals(ticket, events)
  const entries = (Object.keys(signalLabels) as SignalKey[]).flatMap((key) => {
    const value = signals[key]
    return value ? [[key, value] as const] : []
  })

  return (
    <section className="agent-panel agent-signals-panel" aria-labelledby="decision-signals-title">
      <div className="agent-panel-heading">
        <p>Sinais seguros</p>
        <h2 id="decision-signals-title">Base da decisão</h2>
      </div>
      <dl className="agent-signals-list">
        {entries.map(([key, value]) => (
          <div key={key}>
            <dt>{signalLabels[key]}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
