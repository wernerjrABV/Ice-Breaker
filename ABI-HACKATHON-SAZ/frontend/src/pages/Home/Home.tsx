import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  Clock3,
  Send,
  Store,
  Wrench,
} from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react'
import Header from '../../components/Header/Header'
import {
  createTicket,
  getTicket,
  sendMessage,
  sendPhoto,
  sendSerial,
  type Message,
  type Ticket,
  type TicketStatus,
} from '../../clients/client'
import './Home.css'

const DEMO_TICKET = {
  nomePdv: 'Bar do João',
  assunto: 'Congela bebidas',
  descricaoBase: 'Bebidas congelando',
}

const STATUS_LABELS: Record<TicketStatus, string> = {
  em_triagem: 'Em triagem',
  aguardando_confirmacao: 'Aguardando confirmação',
  resolvido_remotamente: 'Resolvido remotamente',
  encaminhado_fornecedor: 'Encaminhado ao fornecedor',
}

function controlledError(error: unknown): string {
  if (
    error instanceof Error
    && /^(Não foi possível|O número de série)/i.test(error.message)
  ) {
    return error.message
  }
  return 'Não foi possível continuar o atendimento. Tente novamente.'
}

function formatMessageTime(createdAt: string): string {
  const date = new Date(createdAt)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatDeadline(deadline: string, now: number): string {
  const date = new Date(deadline)
  if (Number.isNaN(date.getTime())) return 'Prazo de confirmação indisponível'

  const time = new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
  const minutes = Math.max(
    0,
    Math.min(30, Math.ceil((date.getTime() - now) / 60_000)),
  )
  return `Confirmação até ${time} · ${minutes > 0 ? `restam ${minutes} min` : 'prazo encerrado'}`
}

function isUrgentRouting(ticket: Ticket): boolean {
  if (ticket.status !== 'encaminhado_fornecedor') return false
  return ticket.messages.some(
    ({ role, content }) => role === 'assistant'
      && /urgên|sinal de risco|não manipule/i.test(content),
  )
}

function MessageBubble({ item }: { item: Message }) {
  return (
    <li className={`chat-row chat-row-${item.role}`}>
      <article className={`chat-bubble chat-bubble-${item.role}`}>
        <p>{item.content}</p>
        <time dateTime={item.created_at}>{formatMessageTime(item.created_at)}</time>
      </article>
    </li>
  )
}

function Home() {
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [model, setModel] = useState('')
  const [serial, setSerialValue] = useState('')
  const [now, setNow] = useState(() => Date.now())
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true

    async function startTicket() {
      try {
        const created = await createTicket(
          DEMO_TICKET.nomePdv,
          DEMO_TICKET.assunto,
          DEMO_TICKET.descricaoBase,
        )
        const current = await getTicket(created.id)
        if (active) {
          setTicket(current)
          if (current.equipment) {
            setModel(current.equipment.modelo)
            setSerialValue(current.equipment.numero_serie)
          }
        }
      } catch (caught) {
        if (active) setError(controlledError(caught))
      } finally {
        if (active) setLoading(false)
      }
    }

    void startTicket()
    return () => { active = false }
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [ticket?.messages.length])

  useEffect(() => {
    if (ticket?.status !== 'aguardando_confirmacao') return
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [ticket?.status])

  async function runAction(action: () => Promise<unknown>) {
    if (!ticket || busy) return
    setBusy(true)
    setError(null)
    try {
      await action()
      const current = await getTicket(ticket.id)
      setTicket(current)
      if (current.equipment) {
        setModel(current.equipment.modelo)
        setSerialValue(current.equipment.numero_serie)
      }
    } catch (caught) {
      setError(controlledError(caught))
    } finally {
      setBusy(false)
    }
  }

  function handleQuickReply(reply: string) {
    void runAction(() => sendMessage(ticket?.id ?? '', reply))
  }

  function handleTextSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = text.trim()
    if (!content) return
    void runAction(async () => {
      await sendMessage(ticket?.id ?? '', content)
      setText('')
    })
  }

  function handlePhoto(event: ChangeEvent<HTMLInputElement>) {
    const photo = event.target.files?.[0]
    if (!photo) return
    void runAction(() => sendPhoto(ticket?.id ?? '', photo))
    event.target.value = ''
  }

  function handleSerialSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const numeroSerie = serial.trim()
    if (!numeroSerie) {
      setError('O número de série é obrigatório.')
      return
    }
    void runAction(() => sendSerial(ticket?.id ?? '', model.trim(), numeroSerie))
  }

  const finalTicket = ticket?.status === 'resolvido_remotamente'
    || ticket?.status === 'encaminhado_fornecedor'
  const needsManualSerial = ticket?.stage === 'aguardando_identificacao'
    && ticket.equipment !== null
    && (ticket.equipment.confianca < 0.8 || !ticket.equipment.numero_serie.trim())
  const urgentRouting = ticket ? isUrgentRouting(ticket) : false

  return (
    <div className="home">
      <section className="phone-shell" aria-label="Atendimento CoolCare">
        <Header />

        <div className="ticket-context">
          <span className="ticket-context-icon" aria-hidden="true"><Store size={18} /></span>
          <div>
            <strong>{ticket?.nome_pdv ?? DEMO_TICKET.nomePdv}</strong>
            <span>{ticket?.assunto ?? DEMO_TICKET.assunto}</span>
          </div>
          {ticket && (
            <span className={`status-pill status-pill-${ticket.status}`}>
              {STATUS_LABELS[ticket.status]}
            </span>
          )}
        </div>

        {ticket?.status === 'aguardando_confirmacao' && ticket.confirmation_deadline && (
          <div className="deadline-strip" role="status">
            <Clock3 size={16} aria-hidden="true" />
            <span>{formatDeadline(ticket.confirmation_deadline, now)}</span>
          </div>
        )}

        {urgentRouting && (
          <div className="urgent-strip" role="status">
            <AlertTriangle size={17} aria-hidden="true" />
            <span>Aviso urgente: não manipule nem abra o equipamento.</span>
          </div>
        )}

        <main className="chat-area" aria-live="polite">
          {loading && (
            <div className="loading-state">
              <span className="loading-dot" />
              Preparando atendimento…
            </div>
          )}

          <ol className="message-list" aria-label="Mensagens do atendimento">
            {ticket?.messages.map((item, index) => (
              <MessageBubble
                key={item.id ?? `${item.created_at}-${item.role}-${index}`}
                item={item}
              />
            ))}
          </ol>

          {error && <p className="chat-error" role="alert">{error}</p>}

          {ticket?.status === 'resolvido_remotamente' && (
            <section className="result-card result-card-success" aria-label="Resultado do atendimento">
              <CheckCircle2 size={30} aria-hidden="true" />
              <div>
                <span className="result-eyebrow">Atendimento concluído</span>
                <h2>Resolvido remotamente</h2>
                <p>Confirmação positiva registrada. Visita técnica evitada.</p>
              </div>
              <div className="saving-badge">
                <span>Economia estimada</span>
                <strong>R$ 200</strong>
              </div>
            </section>
          )}

          {ticket?.status === 'encaminhado_fornecedor' && (
            <section
              className={`result-card result-card-supplier${urgentRouting ? ' result-card-urgent' : ''}`}
              aria-label="Resultado do atendimento"
            >
              {urgentRouting
                ? <AlertTriangle size={30} aria-hidden="true" />
                : <Wrench size={30} aria-hidden="true" />}
              <div>
                <span className="result-eyebrow">Próximo passo</span>
                <h2>Encaminhado ao fornecedor</h2>
                <p className="supplier-summary-title">Resumo para o fornecedor</p>
                <dl className="supplier-summary">
                  <div><dt>PDV</dt><dd>{ticket.nome_pdv}</dd></div>
                  <div><dt>Chamado</dt><dd>{ticket.assunto}</dd></div>
                  {ticket.equipment && (
                    <div>
                      <dt>Equipamento</dt>
                      <dd>{ticket.equipment.modelo} · {ticket.equipment.numero_serie}</dd>
                    </div>
                  )}
                </dl>
                <p>Histórico, evidências e verificações realizadas seguem com o chamado.</p>
              </div>
            </section>
          )}
          <div ref={chatEndRef} />
        </main>

        {!loading && ticket && !finalTicket && (
          <footer className="composer-area">
            {ticket.stage === 'aguardando_proximidade' && (
              <div className="quick-replies" aria-label="Respostas rápidas">
                <button type="button" disabled={busy} onClick={() => handleQuickReply('Sim')}>Sim</button>
                <button type="button" disabled={busy} onClick={() => handleQuickReply('Não')}>Não</button>
              </div>
            )}

            {ticket.status === 'aguardando_confirmacao' && (
              <div className="quick-replies" aria-label="Respostas rápidas">
                <button type="button" disabled={busy} onClick={() => handleQuickReply('Sim, resolveu')}>
                  Sim, resolveu
                </button>
                <button type="button" disabled={busy} onClick={() => handleQuickReply('Não')}>Não</button>
              </div>
            )}

            {ticket.stage === 'aguardando_identificacao' && (
              <div className="identification-tools">
                <label className={`photo-button${busy ? ' photo-button-disabled' : ''}`}>
                  <Camera size={18} aria-hidden="true" />
                  Foto da etiqueta
                  <input
                    className="photo-input"
                    type="file"
                    accept="image/*"
                    capture="environment"
                    disabled={busy}
                    onChange={handlePhoto}
                  />
                </label>

                {needsManualSerial && (
                  <form
                    className="serial-form"
                    aria-label="Serial manual"
                    onSubmit={handleSerialSubmit}
                  >
                    <p>Leitura incerta. Confirme os dados da etiqueta:</p>
                    <div className="serial-fields">
                      <label>
                        <span>Modelo</span>
                        <input
                          value={model}
                          disabled={busy}
                          onChange={(event) => setModel(event.target.value)}
                        />
                      </label>
                      <label>
                        <span>Número de série</span>
                        <input
                          value={serial}
                          disabled={busy}
                          required
                          onChange={(event) => setSerialValue(event.target.value)}
                        />
                      </label>
                    </div>
                    <button type="submit" disabled={busy || !serial.trim()}>
                      Confirmar equipamento
                    </button>
                  </form>
                )}
              </div>
            )}

            <form className="message-composer" onSubmit={handleTextSubmit}>
              <label className="sr-only" htmlFor="chat-message">Mensagem</label>
              <input
                id="chat-message"
                value={text}
                disabled={busy}
                placeholder="Digite uma mensagem"
                autoComplete="off"
                onChange={(event) => setText(event.target.value)}
              />
              <button type="submit" disabled={busy || !text.trim()} aria-label={busy ? 'Enviando' : 'Enviar'}>
                <Send size={19} aria-hidden="true" />
              </button>
            </form>
          </footer>
        )}
      </section>
    </div>
  )
}

export default Home
