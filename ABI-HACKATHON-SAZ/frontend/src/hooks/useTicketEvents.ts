import { useEffect, useState } from 'react'
import { getTicketEvents, type TicketEvent } from '../clients/client'

export type EventConnection = 'idle' | 'loading' | 'active' | 'reconnecting' | 'complete'

export interface TicketEventsState {
  events: TicketEvent[]
  connection: EventConnection
  error: string | null
}

interface TicketEventsInternalState extends TicketEventsState {
  ticketId: string | null
}

const PAGE_LIMIT = 100
const POLL_MS = 1_000
const RETRY_MS = [1_000, 2_000, 4_000, 5_000] as const

export function useTicketEvents(ticketId: string | null): TicketEventsState {
  const [state, setState] = useState<TicketEventsInternalState>({
    events: [],
    connection: ticketId ? 'loading' : 'idle',
    error: null,
    ticketId,
  })

  useEffect(() => {
    let active = true
    let inFlight = false
    let lastId = 0
    let failures = 0
    let timer: number | undefined

    if (!ticketId) return () => { active = false }

    const schedule = (delay: number) => {
      timer = window.setTimeout(() => { void poll() }, delay)
    }

    const poll = async () => {
      if (!active || inFlight) return
      inFlight = true
      try {
        const response = await getTicketEvents(ticketId, lastId, PAGE_LIMIT)
        if (!active) return
        lastId = Math.max(lastId, response.last_id)
        failures = 0
        setState((current) => {
          const previousEvents = current.ticketId === ticketId ? current.events : []
          const byId = new Map(previousEvents.map((item) => [item.id, item]))
          response.items.forEach((item) => byId.set(item.id, item))
          return {
            events: [...byId.values()].sort((left, right) => left.id - right.id),
            connection: response.terminal ? 'complete' : 'active',
            error: null,
            ticketId,
          }
        })
        if (response.items.length === PAGE_LIMIT) schedule(0)
        else if (!response.terminal) schedule(POLL_MS)
      } catch {
        if (!active) return
        const delay = RETRY_MS[Math.min(failures, RETRY_MS.length - 1)]
        failures += 1
        setState((current) => ({
          events: current.ticketId === ticketId ? current.events : [],
          connection: 'reconnecting',
          error: 'Acompanhamento temporariamente indisponível.',
          ticketId,
        }))
        schedule(delay)
      } finally {
        inFlight = false
      }
    }

    void poll()
    return () => {
      active = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [ticketId])

  if (state.ticketId !== ticketId) {
    return { events: [], connection: ticketId ? 'loading' : 'idle', error: null }
  }

  return state
}
