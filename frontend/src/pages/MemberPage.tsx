import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { getApiErrorMessage } from '../services/apiClient'
import { getMyTickets } from '../services/tickets.service'
import type { TicketPriority, TicketStatus, TicketSummary } from '../types/tickets'

const PAGE_SIZE = 10
const RECENT_TICKET_COUNT = 3

const statusStyles: Record<TicketStatus, string> = {
  OPEN: 'bg-sky-50 text-sky-700 ring-sky-200',
  IN_PROGRESS: 'bg-violet-50 text-violet-700 ring-violet-200',
  RESOLVED: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  CLOSED: 'bg-slate-100 text-slate-600 ring-slate-200',
  REOPENED: 'bg-amber-50 text-amber-800 ring-amber-200',
  ESCALATED: 'bg-rose-50 text-rose-700 ring-rose-200',
}

const priorityStyles: Record<TicketPriority, string> = {
  LOW: 'bg-slate-100 text-slate-600',
  MEDIUM: 'bg-amber-50 text-amber-800',
  HIGH: 'bg-rose-50 text-rose-700',
}

function formatLabel(value: string): string {
  return value.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${statusStyles[status]}`}>
      {formatLabel(status)}
    </span>
  )
}

function PriorityBadge({ priority }: { priority: TicketPriority }) {
  return (
    <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${priorityStyles[priority]}`}>
      {formatLabel(priority)}
    </span>
  )
}

function TicketRows({ tickets }: { tickets: TicketSummary[] }) {
  if (tickets.length === 0) {
    return <p className="px-5 py-10 text-center text-sm text-slate-500">No tickets to show yet.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[850px] border-collapse text-left">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50/70 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <th className="px-5 py-3">Ticket</th>
            <th className="px-5 py-3">Category</th>
            <th className="px-5 py-3">Priority</th>
            <th className="px-5 py-3">Status</th>
            <th className="px-5 py-3">Created</th>
            <th className="px-5 py-3">Last updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tickets.map((ticket) => (
            <tr key={ticket.id} className="align-top hover:bg-slate-50/60">
              <td className="max-w-[320px] px-5 py-4">
                <p className="text-xs font-semibold tracking-wide text-emerald-800">{ticket.ticket_number}</p>
                <p className="mt-1 truncate text-sm font-medium text-slate-900" title={ticket.subject}>{ticket.subject}</p>
              </td>
              <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">{formatLabel(ticket.category)}</td>
              <td className="px-5 py-4"><PriorityBadge priority={ticket.priority} /></td>
              <td className="px-5 py-4"><StatusBadge status={ticket.status} /></td>
              <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">{formatDate(ticket.created_at)}</td>
              <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">{formatDate(ticket.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function MemberPage() {
  const { user, logout } = useAuth()
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [tickets, setTickets] = useState<TicketSummary[]>([])
  const [recentTickets, setRecentTickets] = useState<TicketSummary[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  useEffect(() => {
    let active = true
    setIsLoading(true)
    setError(null)

    getMyTickets(page, PAGE_SIZE)
      .then((result) => {
        if (!active) return
        setTickets(result.items)
        setTotal(result.total)
        if (page === 1) setRecentTickets(result.items.slice(0, RECENT_TICKET_COUNT))
      })
      .catch((requestError: unknown) => {
        if (active) setError(getApiErrorMessage(requestError))
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    return () => { active = false }
  }, [page, refreshKey])

  const firstVisible = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const lastVisible = Math.min(page * PAGE_SIZE, total)

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-6 sm:py-9">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-5 border-b border-slate-200 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-emerald-800">Concave Insights · Support Desk</p>
            <p className="mt-5 text-sm font-medium text-slate-500">Member portal</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Welcome, {user?.name ?? 'Member'}</h1>
            <p className="mt-2 text-sm text-slate-600">Keep track of your support requests in one place.</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium text-slate-800">{user?.name}</p>
              <p className="mt-1 text-xs text-slate-500">{user?.email}</p>
            </div>
            <button type="button" onClick={logout} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
              Sign out
            </button>
          </div>
        </header>

        <section aria-label="Ticket overview" className="mt-6 grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(240px,0.42fr)]">
          <div className="rounded-2xl bg-emerald-900 p-6 text-white shadow-sm sm:p-8">
            <p className="text-sm font-medium text-emerald-100">Your support requests</p>
            <p className="mt-3 text-4xl font-semibold tracking-tight">{error || (isLoading && total === 0) ? '—' : total}</p>
            <p className="mt-2 text-sm text-emerald-100">Total tickets submitted</p>
          </div>
          <div className="flex flex-col justify-center rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <p className="text-sm font-medium text-slate-500">Signed in as</p>
            <p className="mt-2 break-words text-lg font-semibold text-slate-900">{user?.name ?? 'Member'}</p>
            {user?.email && <p className="mt-1 break-all text-sm text-slate-600">{user.email}</p>}
          </div>
        </section>

        <section aria-labelledby="recent-tickets-heading" className="mt-8">
          <div className="mb-3 flex items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">Latest activity</p>
              <h2 id="recent-tickets-heading" className="mt-1 text-xl font-semibold text-slate-950">Recent tickets</h2>
            </div>
            <span className="text-xs text-slate-500">Most recently created</span>
          </div>
          {recentTickets.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-3">
              {recentTickets.map((ticket) => (
                <article key={ticket.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold tracking-wide text-emerald-800">{ticket.ticket_number}</p>
                      <h3 className="mt-1 truncate text-sm font-semibold text-slate-900" title={ticket.subject}>{ticket.subject}</h3>
                    </div>
                    <StatusBadge status={ticket.status} />
                  </div>
                  <p className="mt-3 text-xs text-slate-500">Created {formatDate(ticket.created_at)}</p>
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white px-5 py-6 text-sm text-slate-500">
              {isLoading ? 'Loading recent tickets…' : error ? 'Recent tickets are unavailable right now.' : 'Your recent tickets will appear here.'}
            </div>
          )}
        </section>

        <section aria-labelledby="my-tickets-heading" className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-5 sm:flex-row sm:items-end sm:justify-between sm:px-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">Your requests</p>
              <h2 id="my-tickets-heading" className="mt-1 text-xl font-semibold text-slate-950">My tickets</h2>
              <p className="mt-1 text-sm text-slate-500">Review each ticket’s category, priority, status, and recent dates.</p>
            </div>
            {!isLoading && !error && <p className="text-sm text-slate-500">{total} {total === 1 ? 'ticket' : 'tickets'}</p>}
          </div>

          {error ? (
            <div role="alert" className="px-5 py-10 text-center">
              <p className="font-medium text-slate-900">We couldn’t load your tickets.</p>
              <p className="mt-2 text-sm text-slate-600">{error}</p>
              <button type="button" onClick={() => setRefreshKey((current) => current + 1)} className="mt-4 rounded-lg bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900">
                Try again
              </button>
            </div>
          ) : isLoading ? (
            <div role="status" className="px-5 py-12 text-center text-sm text-slate-600">Loading your tickets…</div>
          ) : total === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="text-base font-semibold text-slate-900">No tickets yet</p>
              <p className="mt-2 text-sm text-slate-600">When you submit a support request, it will appear here.</p>
            </div>
          ) : (
            <>
              <TicketRows tickets={tickets} />
              <div className="flex flex-col gap-3 border-t border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                <p className="text-sm text-slate-500">Showing {firstVisible}–{lastVisible} of {total}</p>
                <nav aria-label="Ticket list pages" className="flex items-center gap-2">
                  <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45">
                    Previous
                  </button>
                  <span className="px-2 text-sm text-slate-600">Page {page} of {pageCount}</span>
                  <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45">
                    Next
                  </button>
                </nav>
              </div>
            </>
          )}
        </section>

        {isLoading && recentTickets.length > 0 && <p className="sr-only" role="status">Refreshing ticket list</p>}
      </div>
    </main>
  )
}
