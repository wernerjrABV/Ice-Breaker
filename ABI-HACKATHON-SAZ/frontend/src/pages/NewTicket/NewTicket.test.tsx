import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import NewTicket from './NewTicket'

const client = vi.hoisted(() => ({
  createDemoTicket: vi.fn(),
}))

vi.mock('../../clients/client', () => client)

beforeEach(() => {
  vi.resetAllMocks()
  window.history.replaceState({}, '', '/')
})

afterEach(() => {
  cleanup()
})

test('opens a ticket from a single free-subject field', async () => {
  const user = userEvent.setup()
  client.createDemoTicket.mockResolvedValue({ id: 'DEMO-1' })

  render(<BrowserRouter><NewTicket /></BrowserRouter>)

  await user.type(screen.getByLabelText('Descreva o chamado'), 'Cooler não gela')
  await user.click(screen.getByRole('button', { name: 'Enviar para triagem' }))

  expect(client.createDemoTicket).toHaveBeenCalledWith('Cooler não gela')
})

test('navigates to the new ticket after triage starts', async () => {
  const user = userEvent.setup()
  client.createDemoTicket.mockResolvedValue({ id: 'DEMO ticket' })

  render(<BrowserRouter><NewTicket /></BrowserRouter>)

  await user.type(screen.getByLabelText('Descreva o chamado'), 'Cooler não gela')
  await user.click(screen.getByRole('button', { name: 'Enviar para triagem' }))

  await waitFor(() => {
    expect(window.location.pathname).toBe('/home')
    expect(new URLSearchParams(window.location.search).get('ticketId')).toBe('DEMO ticket')
  })
})

test('keeps the subject visible when opening the ticket fails', async () => {
  const user = userEvent.setup()
  client.createDemoTicket.mockRejectedValue(new Error('Não foi possível criar o ticket: erro de rede'))

  render(<BrowserRouter><NewTicket /></BrowserRouter>)

  const subject = screen.getByLabelText('Descreva o chamado')
  await user.type(subject, 'Porta não fecha')
  await user.click(screen.getByRole('button', { name: 'Enviar para triagem' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível criar o ticket: erro de rede')
  expect(subject).toHaveValue('Porta não fecha')
})
