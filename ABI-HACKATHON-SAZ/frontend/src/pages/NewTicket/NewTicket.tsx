import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createDemoTicket } from '../../clients/client'
import './NewTicket.css'

function readableError(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'Não foi possível abrir o chamado. Tente novamente.'
}

function NewTicket() {
  const navigate = useNavigate()
  const [subject, setSubject] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedSubject = subject.trim()
    if (!trimmedSubject || busy) return

    setBusy(true)
    setError(null)
    try {
      const ticket = await createDemoTicket(trimmedSubject)
      navigate(`/home?ticketId=${encodeURIComponent(ticket.id)}`)
    } catch (caught) {
      setError(readableError(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="new-ticket" aria-labelledby="new-ticket-title">
      <section className="new-ticket-card">
        <p className="new-ticket-eyebrow">PDV Demonstração</p>
        <h1 id="new-ticket-title">Abra um chamado</h1>
        <p>Descreva o problema do cooler para iniciar a triagem.</p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="ticket-subject">Descreva o chamado</label>
          <textarea
            id="ticket-subject"
            required
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
          />
          {error && <p className="new-ticket-error" role="alert">{error}</p>}
          <button type="submit" disabled={!subject.trim() || busy}>
            {busy ? 'Enviando para triagem…' : 'Enviar para triagem'}
          </button>
        </form>
      </section>
    </main>
  )
}

export default NewTicket
