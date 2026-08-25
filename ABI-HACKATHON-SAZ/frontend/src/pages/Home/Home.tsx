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
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react'
import { AgentDashboard } from '../../components/AgentDashboard/AgentDashboard'
import Header from '../../components/Header/Header'
import {
  expireConfirmations,
  getTicket,
  sendMessage,
  sendPhoto,
  sendSerial,
  type Message,
  type Ticket,
  type TicketStatus,
} from '../../clients/client'
import { useTicketEvents } from '../../hooks/useTicketEvents'
import './Home.css'

const STATUS_LABELS: Record<TicketStatus, string> = {
  em_triagem: 'Em triagem',
  aguardando_confirmacao: 'Aguardando confirmação',
  resolvido_remotamente: 'Resolvido remotamente',
  encaminhado_fornecedor: 'Encaminhado ao fornecedor',
}

const MAX_EXPIRY_ATTEMPTS = 3
const EXPIRY_RETRY_DELAYS_MS = [1_000, 2_000] as const

function ticketIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get('ticketId')?.trim() || null
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
  return ticket.status === 'encaminhado_fornecedor'
    && ticket.priority === 'urgente'
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

function TicketExperience({ requestedTicketId }: { requestedTicketId: string }) {
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshTicketId, setRefreshTicketId] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [model, setModel] = useState('')
  const [serial, setSerialValue] = useState('')
  const [now, setNow] = useState(() => Date.now())
  const chatEndRef = useRef<HTMLDivElement>(null)
  const expiryPromiseRef = useRef<{
    deadline: string
    promise: Promise<Ticket>
  } | null>(null)
  const eventState = useTicketEvents(ticket?.id ?? null)

  const applyTicket = useCallback((current: Ticket) => {
    setTicket(current)
    if (current.equipment) {
      setModel(current.equipment.modelo)
      setSerialValue(current.equipment.numero_serie)
    }
  }, [])

  useEffect(() => {
    let active = true

    async function startTicket() {
      try {
        const current = await getTicket(requestedTicketId)
        if (active) {
          applyTicket(current)
        }
      } catch (caught) {
        if (active) setError(controlledError(caught))
      } finally {
        if (active) setLoading(false)
      }
    }

    void startTicket()
    return () => { active = false }
  }, [applyTicket, requestedTicketId])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [ticket?.messages.length])

  const ticketStatus = ticket?.status
  const ticketDeadline = ticket?.confirmation_deadline
  const ticketId = ticket?.id

  useEffect(() => {
    if (
      ticketStatus !== 'aguardando_confirmacao'
      || !ticketDeadline
      || !ticketId
    ) return

    const deadline = ticketDeadline
    const expiringTicketId: string = ticketId
    const deadlineTime = new Date(deadline).getTime()
    if (Number.isNaN(deadlineTime)) return

    let active = true
    let expiryRequested = false
    let expiryAttempts = 0
    let retryTimer: number | undefined

    function requestExpiry(): Promise<Ticket> {
      const existing = expiryPromiseRef.current
      if (existing?.deadline === deadline) return existing.promise

      const promise = expireConfirmations().then(() => getTicket(expiringTicketId))
      expiryPromiseRef.current = { deadline, promise }
      return promise
    }

    async function expireDeadline() {
      if (!active || expiryRequested || expiryAttempts >= MAX_EXPIRY_ATTEMPTS) return
      expiryRequested = true
      expiryAttempts += 1
      setBusy(true)
      setError(null)
      const request = requestExpiry()
      let shouldRetry = false
      try {
        const current = await request
        if (active) {
          applyTicket(current)
          shouldRetry = current.status === 'aguardando_confirmacao'
            && current.confirmation_deadline === deadline
        }
      } catch (caught) {
        if (active) setError(controlledError(caught))
      } finally {
        if (expiryPromiseRef.current?.promise === request) {
          expiryPromiseRef.current = null
        }
        expiryRequested = false
        if (active) {
          setBusy(false)
          if (shouldRetry && expiryAttempts < MAX_EXPIRY_ATTEMPTS) {
            const delay = EXPIRY_RETRY_DELAYS_MS[expiryAttempts - 1]
              ?? EXPIRY_RETRY_DELAYS_MS.at(-1)
              ?? 1_000
            retryTimer = window.setTimeout(() => { void expireDeadline() }, delay)
          }
        }
      }
    }

    function tick() {
      const currentTime = Date.now()
      setNow(currentTime)
      if (currentTime >= deadlineTime) void expireDeadline()
    }

    tick()
    const clockTimer = window.setInterval(tick, 30_000)
    const expiryTimer = window.setTimeout(
      tick,
      Math.max(0, deadlineTime - Date.now()),
    )
    return () => {
      active = false
      window.clearInterval(clockTimer)
      window.clearTimeout(expiryTimer)
      if (retryTimer !== undefined) window.clearTimeout(retryTimer)
    }
  }, [applyTicket, ticketDeadline, ticketId, ticketStatus])

  async function runAction(action: () => Promise<Ticket>) {
    if (!ticket || busy) return
    const ticketId = ticket.id
    setBusy(true)
    setError(null)
    setRefreshTicketId(null)
    try {
      const updated = await action()
      applyTicket(updated)
      try {
        applyTicket(await getTicket(ticketId))
      } catch (caught) {
        setRefreshTicketId(ticketId)
        setError(controlledError(caught))
      }
    } catch (caught) {
      setError(controlledError(caught))
    } finally {
      setBusy(false)
    }
  }

  async function handleRefreshRetry() {
    if (!refreshTicketId || busy) return
    setBusy(true)
    setError(null)
    try {
      applyTicket(await getTicket(refreshTicketId))
      setRefreshTicketId(null)
    } catch (caught) {
      setError(controlledError(caught))
    } finally {
      setBusy(false)
    }
  }

  async function handleStartupRetry() {
    setLoading(true)
    setError(null)
    try {
      const current = await getTicket(requestedTicketId)
      applyTicket(current)
    } catch (caught) {
      setError(controlledError(caught))
    } finally {
      setLoading(false)
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
      const updated = await sendMessage(ticket?.id ?? '', content)
      setText('')
      return updated
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
    && (
      ticket.equipment.confianca < 0.8
      || !ticket.equipment.numero_serie.trim()
      || ticket.outcome_reason === 'correcao_identificacao_necessaria'
    )
  const urgentRouting = ticket ? isUrgentRouting(ticket) : false

  return (
    <div className="home">
      <main className="case-experience" aria-label="Experiência do chamado">
      <section className="phone-shell phone-shell-flex" aria-label="Atendimento CoolCare">
        <Header />

        <div className="ticket-context">
          <span className="ticket-context-icon" aria-hidden="true"><Store size={18} /></span>
          <div>
            <strong>{ticket?.nome_pdv ?? 'Chamado'}</strong>
            <span>{ticket?.assunto ?? 'Carregando chamado'}</span>
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

        <section
          className="chat-area chat-area-flexible"
          aria-label="Conversa do atendimento"
          aria-live="polite"
        >
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
          {error && !ticket && !loading && (
            <button
              type="button"
              className="startup-retry"
              onClick={() => { void handleStartupRetry() }}
            >
              Tentar novamente
            </button>
          )}
          {error && ticket && refreshTicketId && (
            <button
              type="button"
              className="startup-retry"
              disabled={busy}
              onClick={() => { void handleRefreshRetry() }}
            >
              Tentar atualizar
            </button>
          )}

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
                {ticket.supplier_summary && (
                  <>
                    <p className="supplier-summary-title">Resumo para o fornecedor</p>
                    <dl className="supplier-summary">
                      <div><dt>PDV</dt><dd>{ticket.supplier_summary.nome_pdv}</dd></div>
                      <div><dt>Chamado</dt><dd>{ticket.supplier_summary.assunto}</dd></div>
                      {ticket.supplier_summary.equipamento && (
                        <div>
                          <dt>Equipamento</dt>
                          <dd>
                            {ticket.supplier_summary.equipamento.tipo} ·{' '}
                            {ticket.supplier_summary.equipamento.modelo} ·{' '}
                            {ticket.supplier_summary.equipamento.numero_serie}
                            {ticket.supplier_summary.equipamento.foto_etiqueta
                              ? ` · ${ticket.supplier_summary.equipamento.foto_etiqueta}`
                              : ''}
                          </dd>
                        </div>
                      )}
                      <div>
                        <dt>Prioridade</dt>
                        <dd className="supplier-priority">
                          Prioridade {ticket.supplier_summary.prioridade}
                        </dd>
                      </div>
                      <div><dt>Motivo</dt><dd>{ticket.supplier_summary.motivo}</dd></div>
                    </dl>
                    <section className="supplier-details" aria-label="Evidências para o fornecedor">
                      <h3>Evidências</h3>
                      {ticket.supplier_summary.evidencias.length > 0 ? (
                        <ul>
                          {ticket.supplier_summary.evidencias.map((item, index) => (
                            <li key={`${item.tipo}-${index}`}>{item.descricao}</li>
                          ))}
                        </ul>
                      ) : <p>Nenhuma evidência adicional registrada.</p>}
                    </section>
                    <section className="supplier-details" aria-label="Ações tentadas para o fornecedor">
                      <h3>Ações tentadas</h3>
                      {ticket.supplier_summary.acoes_tentadas.length > 0 ? (
                        <ul>
                          {ticket.supplier_summary.acoes_tentadas.map((action, index) => (
                            <li key={`${index}-${action}`}>{action}</li>
                          ))}
                        </ul>
                      ) : <p>Nenhuma verificação remota foi realizada.</p>}
                    </section>
                  </>
                )}
              </div>
            </section>
          )}
          <div ref={chatEndRef} />
        </section>

        {!loading && ticket && !finalTicket && (
          <footer className="composer-area composer-pinned">
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

            {ticket.stage === 'aguardando_confirmacao_equipamento' && ticket.equipment && (
              <>
                <section
                  className="equipment-confirmation"
                  aria-label="Confirmação do equipamento"
                >
                  <span>Modelo</span>
                  <strong>{ticket.equipment.modelo || 'Não informado'}</strong>
                  <span>Número de série</span>
                  <strong>{ticket.equipment.numero_serie}</strong>
                  {ticket.equipment.image_name && (
                    <small>Foto da etiqueta: {ticket.equipment.image_name}</small>
                  )}
                </section>
                <div className="quick-replies" aria-label="Confirmar dados do equipamento">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleQuickReply('Sim, dados corretos')}
                  >
                    Sim, dados corretos
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleQuickReply('Não, corrigir')}
                  >
                    Não, corrigir
                  </button>
                </div>
              </>
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
      {ticket && (
        <AgentDashboard
          ticket={ticket}
          events={eventState.events}
          connection={eventState.connection}
          error={eventState.error}
        />
      )}
      </main>
    </div>
  )
}

function Home() {
  const requestedTicketId = ticketIdFromUrl()
  if (!requestedTicketId) {
    return (
      <main className="home home-empty" aria-label="Atendimento CoolCare">
        <p className="chat-error" role="alert">Abra um chamado para iniciar o atendimento.</p>
        <a className="startup-retry" href="/">Abrir um chamado</a>
      </main>
    )
  }

  return <TicketExperience requestedTicketId={requestedTicketId} />
}

export default Home
