import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PriorityBadge, StatusBadge, formatTicketLabel } from '../components/common/TicketBadges'
import { getApiErrorMessage } from '../services/apiClient'
import { assignSupportTicket, getAssignableAgents, getSupportTicket } from '../services/tickets.service'
import type { TicketDetail, TicketUserSummary } from '../types/tickets'

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
  const [agents, setAgents] = useState<TicketUserSummary[]>([])
  const [agentsLoading, setAgentsLoading] = useState(true)
  const [agentsError, setAgentsError] = useState<string | null>(null)
  const [assignmentBusy, setAssignmentBusy] = useState(false)
  const [assignmentError, setAssignmentError] = useState<string | null>(null)
  const [assignmentSuccess, setAssignmentSuccess] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState('')

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

  useEffect(() => {
    let active = true
    setAgentsLoading(true)
    setAgentsError(null)
    getAssignableAgents()
      .then((result) => { if (active) setAgents(result) })
      .catch((requestError: unknown) => { if (active) setAgentsError(getApiErrorMessage(requestError)) })
      .finally(() => { if (active) setAgentsLoading(false) })
    return () => { active = false }
  }, [ticketId])

  useEffect(() => {
    setSelectedAgent(ticket?.assigned_to ? String(ticket.assigned_to.id) : '')
  }, [ticket?.id, ticket?.assigned_to?.id])

  async function handleAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ticket || !selectedAgent || assignmentBusy) return
    setAssignmentBusy(true)
    setAssignmentError(null)
    setAssignmentSuccess(null)
    try {
      const updated = await assignSupportTicket(ticket.id, Number(selectedAgent))
      setTicket(updated)
      setAssignmentSuccess(`Ticket assigned to ${updated.assigned_to?.name ?? 'the selected agent'}.`)
    } catch (requestError) {
      setAssignmentError(getApiErrorMessage(requestError))
    } finally {
      setAssignmentBusy(false)
    }
  }

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
                <form onSubmit={handleAssignment} className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-5">
                  <h3 className="text-sm font-semibold text-slate-900">{ticket.assigned_to ? 'Reassign ticket' : 'Assign ticket'}</h3>
                  <p className="mt-1 text-sm text-slate-600">Choose an active support agent for this ticket.</p>
                  <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
                    <div className="min-w-0 flex-1">
                      <label htmlFor="assigned-agent" className="mb-1 block text-sm font-medium text-slate-700">Support agent</label>
                      <select id="assigned-agent" value={selectedAgent} onChange={(event) => { setSelectedAgent(event.target.value); setAssignmentError(null); setAssignmentSuccess(null) }} disabled={agentsLoading || agents.length === 0 || assignmentBusy} className="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-100">
                        <option value="">{agentsLoading ? 'Loading agents…' : agents.length === 0 ? 'No active agents available' : 'Select an agent'}</option>
                        {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name} ({agent.email})</option>)}
                      </select>
                    </div>
                    <button type="submit" disabled={assignmentBusy || agentsLoading || agents.length === 0 || !selectedAgent || String(ticket.assigned_to?.id ?? '') === selectedAgent} className="min-h-11 rounded-lg bg-emerald-800 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">{assignmentBusy ? 'Saving…' : ticket.assigned_to ? 'Reassign ticket' : 'Assign ticket'}</button>
                  </div>
                  {agentsError && <p role="alert" className="mt-3 text-sm text-rose-700">Available agents could not be loaded: {agentsError}</p>}
                  {!agentsLoading && !agentsError && agents.length === 0 && <p className="mt-3 text-sm text-slate-600">There are no active support agents available to receive assignments.</p>}
                  {assignmentError && <p role="alert" className="mt-3 text-sm text-rose-700">Assignment failed: {assignmentError}</p>}
                  {assignmentSuccess && <p role="status" className="mt-3 text-sm text-emerald-800">{assignmentSuccess}</p>}
                </form>
                <div className="mt-6 border-t border-slate-100 pt-5"><h3 className="text-sm font-semibold text-slate-900">Description</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{ticket.description}</p></div>
              </section>
            </> : null}
      </div>
    </main>
  )
}
