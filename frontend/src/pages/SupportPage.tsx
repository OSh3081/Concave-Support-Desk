import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { PriorityBadge, StatusBadge, formatTicketLabel } from '../components/common/TicketBadges'
import { getApiErrorMessage } from '../services/apiClient'
import { getSupportTickets } from '../services/tickets.service'
import type { TicketSummary } from '../types/tickets'

const PAGE_SIZE = 10

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

export default function SupportPage() {
  const { user, logout } = useAuth()
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [tickets, setTickets] = useState<TicketSummary[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const isPageOutOfRange = page > pageCount

  useEffect(() => {
    let active = true
    setIsLoading(true)
    setError(null)
    getSupportTickets(page, PAGE_SIZE)
      .then((result) => {
        if (!active) return
        setTickets(result.items)
        setTotal(result.total)
      })
      .catch((requestError: unknown) => {
        if (active) setError(getApiErrorMessage(requestError))
      })
      .finally(() => { if (active) setIsLoading(false) })
    return () => { active = false }
  }, [page, refreshKey])

  useEffect(() => {
    if (page > pageCount) setPage(pageCount)
  }, [page, pageCount])

  const firstVisible = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const lastVisible = Math.min(page * PAGE_SIZE, total)

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-6 sm:py-9">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 rounded-2xl bg-emerald-950 px-5 py-6 text-white shadow-sm sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">Support agent workspace</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Ticket queue</h1>
            <p className="mt-2 text-sm text-emerald-100">Review incoming requests and open a ticket to see its details.</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-emerald-100 sm:inline">{user?.name}</span>
            <button type="button" aria-label="Refresh ticket queue" disabled={isLoading} onClick={() => setRefreshKey((value) => value + 1)} className="min-h-10 rounded-lg border border-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white disabled:cursor-not-allowed disabled:opacity-50">Refresh</button>
            <button type="button" onClick={() => { void logout() }} className="min-h-10 rounded-lg border border-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">Sign out</button>
          </div>
        </header>

        <section aria-labelledby="queue-heading" className="mt-7 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-1 border-b border-slate-200 px-5 py-5 sm:flex-row sm:items-end sm:justify-between sm:px-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">All available tickets</p>
              <h2 id="queue-heading" className="mt-1 text-xl font-semibold text-slate-950">Support queue</h2>
            </div>
            {!isLoading && !isPageOutOfRange && !error && <p className="text-sm text-slate-500">{total} {total === 1 ? 'ticket' : 'tickets'}</p>}
          </div>

          {error ? (
            <div role="alert" className="px-5 py-10 text-center">
              <p className="font-medium text-slate-900">We couldn’t load the support queue.</p>
              <p className="mt-2 text-sm text-slate-600">{error}</p>
              <button type="button" onClick={() => setRefreshKey((value) => value + 1)} className="mt-5 min-h-10 rounded-lg bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700">Try again</button>
            </div>
          ) : isLoading || isPageOutOfRange ? (
            <div role="status" className="px-5 py-12 text-center text-sm text-slate-600">{isPageOutOfRange ? 'Updating queue page…' : 'Loading support queue…'}</div>
          ) : tickets.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="font-medium text-slate-900">No tickets in the queue</p>
              <p className="mt-1 text-sm text-slate-500">New support requests will appear here.</p>
            </div>
          ) : (
            <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700" tabIndex={0} role="region" aria-label="Support ticket queue. Scroll horizontally to see all columns.">
              <table className="w-full min-w-[900px] border-collapse text-left">
                <thead><tr className="border-b border-slate-200 bg-slate-50/70 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-3">Ticket</th><th className="px-5 py-3">Category</th><th className="px-5 py-3">Priority</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Created</th><th className="px-5 py-3">Assigned agent</th>
                </tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {tickets.map((ticket) => <tr key={ticket.id} className="align-top hover:bg-slate-50/60">
                    <td className="max-w-[320px] px-5 py-4"><Link to={`/support/tickets/${ticket.id}`} className="group block rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700"><span className="text-xs font-semibold tracking-wide text-emerald-800 group-hover:underline">{ticket.ticket_number}</span><span className="mt-1 block truncate text-sm font-medium text-slate-900 group-hover:text-emerald-900" title={ticket.subject}>{ticket.subject}</span></Link></td>
                    <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">{formatTicketLabel(ticket.category)}</td>
                    <td className="px-5 py-4"><PriorityBadge priority={ticket.priority} /></td>
                    <td className="px-5 py-4"><StatusBadge status={ticket.status} /></td>
                    <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">{formatDate(ticket.created_at)}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{ticket.assigned_to?.name ?? 'Unassigned'}</td>
                  </tr>)}
                </tbody>
              </table>
            </div>
          )}

          {!error && !isLoading && !isPageOutOfRange && total > 0 && <nav aria-label="Ticket queue pages" className="flex flex-col gap-3 border-t border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <p className="text-sm text-slate-600">Showing {firstVisible}–{lastVisible} of {total}</p>
            <div className="flex gap-2">
              <button type="button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="min-h-10 rounded-lg border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Previous</button>
              <span className="self-center px-2 text-sm text-slate-600">Page {page} of {pageCount}</span>
              <button type="button" disabled={page >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))} className="min-h-10 rounded-lg border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Next</button>
            </div>
          </nav>}
        </section>
      </div>
    </main>
  )
}
