import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PriorityBadge, StatusBadge, formatTicketLabel } from '../components/common/TicketBadges'
import { getApiErrorMessage } from '../services/apiClient'
import { getSupportTicket } from '../services/tickets.service'
import type { TicketDetail } from '../types/tickets'

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export default function SupportTicketDetailPage() {
  const { ticketId } = useParams()
  const [ticket, setTicket] = useState<TicketDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setTicket(null)
    const id = Number(ticketId)
    if (!Number.isInteger(id) || id < 1) {
      setError('This ticket link is invalid.')
      setIsLoading(false)
      return () => { active = false }
    }
    setIsLoading(true)
    setError(null)
    getSupportTicket(id)
      .then((result) => {
        if (result.id !== id) {
          throw new Error(`Requested ticket ${id}, but the server returned ticket ${result.id}.`)
        }
        if (active) setTicket(result)
      })
      .catch((requestError: unknown) => {
        if (active) setError(getApiErrorMessage(requestError))
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => { active = false }
  }, [ticketId])

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-6 sm:py-9">
      <div className="mx-auto max-w-4xl">
        <Link to="/support" className="text-sm font-semibold text-emerald-800 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700">← Back to queue</Link>
        {isLoading ? <div role="status" className="mt-5 rounded-2xl border border-slate-200 bg-white px-5 py-12 text-center text-sm text-slate-600">Loading ticket…</div>
          : error ? <section role="alert" className="mt-5 rounded-2xl border border-rose-200 bg-white px-5 py-10 text-center"><p className="font-medium text-slate-900">We couldn’t open this ticket.</p><p className="mt-2 text-sm text-slate-600">{error}</p></section>
            : ticket ? <>
              <header className="mt-5 rounded-2xl bg-emerald-950 px-5 py-6 text-white shadow-sm sm:px-8">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">{ticket.ticket_number}</p>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{ticket.subject}</h1>
                <div className="mt-4 flex flex-wrap items-center gap-3"><StatusBadge status={ticket.status} /><PriorityBadge priority={ticket.priority} /><span className="text-sm text-emerald-100">{formatTicketLabel(ticket.category)}</span></div>
              </header>
              <section aria-labelledby="ticket-details" className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
                <h2 id="ticket-details" className="text-lg font-semibold text-slate-950">Ticket details</h2>
                <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
                  <div><dt className="text-slate-500">Created</dt><dd className="mt-1 font-medium text-slate-900">{formatDate(ticket.created_at)}</dd></div>
                  <div><dt className="text-slate-500">Assigned agent</dt><dd className="mt-1 font-medium text-slate-900">{ticket.assigned_to?.name ?? 'Unassigned'}</dd></div>
                  <div><dt className="text-slate-500">Member</dt><dd className="mt-1 font-medium text-slate-900">{ticket.member.name}</dd></div>
                  <div><dt className="text-slate-500">SLA due</dt><dd className="mt-1 font-medium text-slate-900">{formatDate(ticket.due_at)}</dd></div>
                </dl>
                <div className="mt-6 border-t border-slate-100 pt-5"><h3 className="text-sm font-semibold text-slate-900">Description</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{ticket.description}</p></div>
              </section>
            </> : null}
      </div>
    </main>
  )
}
