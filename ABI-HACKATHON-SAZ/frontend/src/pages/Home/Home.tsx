import { useEffect, useState, type FormEvent } from 'react'
import { RefreshCw } from 'lucide-react'
import Header from '../../components/Header/Header'
import Footer from '../../components/Footer/Footer'
import Card from '../../components/Card/Card'
import Input from '../../components/Input/Input'
import Button from '../../components/Button/Button'
import hackathonImage from '../../assets/hackathon.png'
import { createKickoffRequest, listKickoffRequests, type KickoffRequest } from '../../clients/client'
import './Home.css'

function getErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function getStatusLabel(status: string): string {
  const statusLabels: Record<string, string> = {
    pending: 'Pendente',
    completed: 'Concluída',
    failed: 'Com falha',
  }

  return statusLabels[status] ?? status
}

function Home() {
  const [subject, setSubject] = useState('')
  const [requests, setRequests] = useState<KickoffRequest[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    refreshRequests()
  }, [])

  async function refreshRequests() {
    try {
      const list = await listKickoffRequests()
      setRequests(list)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!subject.trim() || submitting) return

    setSubmitting(true)
    setError(null)
    try {
      await createKickoffRequest(subject.trim())
      setSubject('')
      await refreshRequests()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const sortedRequests = [...requests].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )

  return (
    <div className="home">
      <Header />

      <main className="home-main">
        <h2 className="home-question">Bem-vindo(a) ao projeto template do</h2>
        <h1 className="home-question">Hackaton SAZ - Grand Slam</h1>
        <img className="home-image" src={hackathonImage} alt="Hackathon SAZ - Grand Slam" />
        <p className="home-question">
          Este template é um exemplo de aplicação completa que se conecta com backend, banco de dados e agentes CrewAI. <br /><br />
          Teste esta aplicação digitando um assunto qualquer abaixo para começar! <br />
          Não se esqueça de executar os 3 projetos (frontend, backend e agent) e incluir sua chave de API no arquivo agent/.env.
        </p>

        <form className="home-form" onSubmit={handleSubmit}>
          <Input
            className="home-input"
            placeholder="Digite um assunto..."
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
          />
          <Button type="submit" disabled={submitting || !subject.trim()}>
            {submitting ? 'Consultando...' : 'Consultar'}
          </Button>
        </form>

        {error && <p className="home-error">{error}</p>}

        <section className="home-results">
          <div className="home-results-header">
            <h3>Resultados</h3>
            <button
              type="button"
              className="home-refresh"
              onClick={refreshRequests}
              aria-label="Atualizar resultados"
            >
              <RefreshCw size={16} />
              Atualizar
            </button>
          </div>

          {sortedRequests.length === 0 && <p className="home-empty">Ainda não há solicitações.</p>}

          <ul className="home-results-list">
            {sortedRequests.map((request) => (
              <li key={request.id}>
                <Card className="home-result-card">
                  <div className="home-result-meta">
                    <span className="home-result-id">{request.id}</span>
                    <span className={`home-result-status home-result-status-${request.status}`}>
                      {getStatusLabel(request.status)}
                    </span>
                  </div>
                  <p className="home-result-subject">{request.input?.subject}</p>
                  {request.result && <p className="home-result-text">{request.result}</p>}
                  {request.error && <p className="home-result-error">{request.error}</p>}
                </Card>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default Home
