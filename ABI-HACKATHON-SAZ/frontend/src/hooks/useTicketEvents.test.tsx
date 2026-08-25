import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { TicketEvent, TicketEventsResponse } from '../clients/client'

const getTicketEvents = vi.hoisted(() => vi.fn())

vi.mock('../clients/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../clients/client')>(),
  getTicketEvents,
}))

import * as client from '../clients/client'
import { useTicketEvents } from './useTicketEvents'

const mockedGetTicketEvents = vi.mocked(client.getTicketEvents)

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

function event(id: number): TicketEvent {
  return {
    id,
    ticket_id: 'T-1',
    category: 'ticket_created',
    title: 'Ticket criado',
    description: 'O ticket foi criado.',
    state: 'completed',
    metadata: {},
    created_at: '2026-08-25T17:32:09Z',
  }
}

test('polls incrementally without concurrent requests and stops when terminal', async () => {
  vi.useFakeTimers()
  let finishSecond: ((value: TicketEventsResponse) => void) | undefined
  mockedGetTicketEvents
    .mockResolvedValueOnce({ items: [event(1)], last_id: 1, terminal: false })
    .mockImplementationOnce(() => new Promise((resolve) => { finishSecond = resolve }))

  const { result } = renderHook(() => useTicketEvents('T-1'))
  await act(async () => undefined)
  expect(mockedGetTicketEvents).toHaveBeenNthCalledWith(1, 'T-1', 0, 100)

  await act(async () => { vi.advanceTimersByTime(1_000) })
  expect(mockedGetTicketEvents).toHaveBeenNthCalledWith(2, 'T-1', 1, 100)
  await act(async () => { vi.advanceTimersByTime(3_000) })
  expect(mockedGetTicketEvents).toHaveBeenCalledTimes(2)

  await act(async () => {
    finishSecond?.({ items: [event(2)], last_id: 2, terminal: true })
  })
  await act(async () => { vi.advanceTimersByTime(5_000) })
  expect(mockedGetTicketEvents).toHaveBeenCalledTimes(2)
  expect(result.current.events.map((item) => item.id)).toEqual([1, 2])
  expect(result.current.connection).toBe('complete')
})

test('drains a full page immediately and deduplicates ids', async () => {
  vi.useFakeTimers()
  const fullPage = Array.from({ length: 100 }, (_, index) => event(index + 1))
  mockedGetTicketEvents
    .mockResolvedValueOnce({ items: fullPage, last_id: 100, terminal: false })
    .mockResolvedValueOnce({ items: [event(100), event(101)], last_id: 101, terminal: false })

  const { result } = renderHook(() => useTicketEvents('T-1'))
  await act(async () => undefined)
  await act(async () => { vi.advanceTimersByTime(0) })

  expect(mockedGetTicketEvents).toHaveBeenNthCalledWith(2, 'T-1', 100, 100)
  expect(result.current.events).toHaveLength(101)
})

test('keeps events and backs off at one, two, four, then five seconds', async () => {
  vi.useFakeTimers()
  mockedGetTicketEvents
    .mockResolvedValueOnce({ items: [event(1)], last_id: 1, terminal: false })
    .mockRejectedValueOnce(new Error('offline'))
    .mockRejectedValueOnce(new Error('offline'))
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce({ items: [event(2)], last_id: 2, terminal: false })

  const { result } = renderHook(() => useTicketEvents('T-1'))
  await act(async () => undefined)
  for (const delay of [1_000, 1_000, 2_000, 4_000]) {
    await act(async () => { vi.advanceTimersByTime(delay) })
  }

  expect(result.current.events.map((item) => item.id)).toEqual([1, 2])
  expect(result.current.connection).toBe('active')
})
