import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PriorityBadge, StatusBadge, formatTicketLabel } from '../components/common/TicketBadges'
import TicketConversation from '../components/tickets/TicketConversation'
import TicketHistory from '../components/tickets/TicketHistory'
import { getApiErrorMessage } from '../services/apiClient'
import { assignSupportTicket, changeSupportTicketPriority, changeSupportTicketStatus, getAssignableAgents, getSupportTicket, replyToTicket } from '../services/tickets.service'
import type { TicketDetail, TicketPriority, TicketStatus, TicketUserSummary } from '../types/tickets'

// Mirrors the transitions accepted by backend/app/services/tickets.py.
const supportStatusTransitions: Partial<Record<TicketStatus, TicketStatus[]>> = {
  OPEN: ['IN_PROGRESS', 'ESCALATED'],
  IN_PROGRESS: ['RESOLVED', 'ESCALATED'],
  REOPENED: ['IN_PROGRESS', 'ESCALATED'],
  ESCALATED: ['IN_PROGRESS', 'RESOLVED'],
}

const ticketPriorities: TicketPriority[] = ['LOW', 'MEDIUM', 'HIGH']

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function characterCount(value: string): number {
  return Array.from(value).length
}

export default function SupportTicketDetailPage() {
  const { ticketId } = useParams()
  const activeTicketId = useRef(Number(ticketId))
  const activeTicketGeneration = useRef(0)
  const previousTicketId = useRef(ticketId)
  if (previousTicketId.current !== ticketId) {
    previousTicketId.current = ticketId
    activeTicketGeneration.current += 1
  }
  activeTicketId.current = Number(ticketId)
  const replyInFlight = useRef(false)
  const statusInFlight = useRef(new Set<number>())
  const [statusPendingTicketIds, setStatusPendingTicketIds] = useState<Set<number>>(() => new Set())
  const priorityInFlight = useRef(new Set<number>())
  const [priorityPendingTicketIds, setPriorityPendingTicketIds] = useState<Set<number>>(() => new Set())
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
  const [selectedStatus, setSelectedStatus] = useState<TicketStatus | ''>('')
  const [statusReason, setStatusReason] = useState('')
  const [statusError, setStatusError] = useState<string | null>(null)
  const [statusSuccess, setStatusSuccess] = useState<string | null>(null)
  const [statusRefreshWarning, setStatusRefreshWarning] = useState<string | null>(null)
  const [selectedPriority, setSelectedPriority] = useState<TicketPriority | ''>('')
  const [priorityReason, setPriorityReason] = useState('')
  const [priorityError, setPriorityError] = useState<string | null>(null)
  const [prioritySuccess, setPrioritySuccess] = useState<string | null>(null)
  const [priorityRefreshWarning, setPriorityRefreshWarning] = useState<string | null>(null)
  const [replyMessage, setReplyMessage] = useState('')
  const [replyMode, setReplyMode] = useState<'public' | 'internal' | 'request_information'>('public')
  const [replyBusy, setReplyBusy] = useState(false)
  const [replyError, setReplyError] = useState<string | null>(null)
  const [replySuccess, setReplySuccess] = useState<string | null>(null)
  const [replyRefreshWarning, setReplyRefreshWarning] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setTicket(null)
    setReplyMessage('')
    setReplyMode('public')
    setReplyBusy(false)
    setReplyError(null)
    setReplySuccess(null)
    setReplyRefreshWarning(null)
    setStatusError(null)
    setStatusSuccess(null)
    setStatusRefreshWarning(null)
    setStatusReason('')
    setPriorityReason('')
    setPriorityError(null)
    setPrioritySuccess(null)
    setPriorityRefreshWarning(null)
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

  const availableStatusTransitions = ticket ? supportStatusTransitions[ticket.status] ?? [] : []
  const statusBusy = ticket ? statusPendingTicketIds.has(ticket.id) : false
  const availablePriorities = ticket ? ticketPriorities.filter((priority) => priority !== ticket.priority) : []
  const priorityBusy = ticket ? priorityPendingTicketIds.has(ticket.id) : false

  useEffect(() => {
    setSelectedStatus(availableStatusTransitions[0] ?? '')
    setStatusReason('')
    setStatusError(null)
    setStatusRefreshWarning(null)
  }, [ticket?.id, ticket?.status])

  useEffect(() => {
    setSelectedPriority(availablePriorities[0] ?? '')
    setPriorityReason('')
    setPriorityError(null)
    setPriorityRefreshWarning(null)
  }, [ticket?.id, ticket?.priority])

  async function handleStatusChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ticket || statusInFlight.current.has(ticket.id) || statusBusy || ticket.id !== activeTicketId.current) return
    if (!selectedStatus || !availableStatusTransitions.includes(selectedStatus)) return
    if (selectedStatus === 'ESCALATED' && !statusReason.trim()) {
      setStatusError('Enter a reason before escalating this ticket.')
      return
    }

    const submittedTicketId = ticket.id
    const submittedTicketGeneration = activeTicketGeneration.current
    const targetStatus = selectedStatus
    const isSubmittedTicketViewActive = () =>
      activeTicketId.current === submittedTicketId &&
      activeTicketGeneration.current === submittedTicketGeneration

    statusInFlight.current.add(submittedTicketId)
    setStatusPendingTicketIds((pendingIds) => new Set(pendingIds).add(submittedTicketId))
    setStatusError(null)
    setStatusSuccess(null)
    setStatusRefreshWarning(null)
    try {
      const updatedTicket = await changeSupportTicketStatus(submittedTicketId, {
        status: targetStatus,
        ...(targetStatus === 'ESCALATED' ? { reason: statusReason.trim() } : {}),
      })
      if (!isSubmittedTicketViewActive()) return
      if (updatedTicket.id !== submittedTicketId) {
        throw new Error('The server returned a different ticket. Reload this ticket before continuing.')
      }
      setTicket(updatedTicket)
      const successMessage = `Ticket status changed to ${formatTicketLabel(updatedTicket.status)}.`
      try {
        const refreshedTicket = await getSupportTicket(submittedTicketId)
        if (!isSubmittedTicketViewActive()) return
        if (refreshedTicket.id !== submittedTicketId) {
          throw new Error('The server returned a different ticket than requested.')
        }
        setTicket(refreshedTicket)
        setStatusSuccess(successMessage)
      } catch {
        if (isSubmittedTicketViewActive()) {
          setStatusRefreshWarning('The status change was saved, but the ticket could not be refreshed. The saved ticket and history are shown; reload to check for newer updates.')
          setStatusSuccess(successMessage)
        }
      }
    } catch (requestError) {
      if (isSubmittedTicketViewActive()) setStatusError(getApiErrorMessage(requestError))
    } finally {
      statusInFlight.current.delete(submittedTicketId)
      setStatusPendingTicketIds((pendingIds) => {
        const nextPendingIds = new Set(pendingIds)
        nextPendingIds.delete(submittedTicketId)
        return nextPendingIds
      })
    }
  }

  async function handlePriorityChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ticket || priorityInFlight.current.has(ticket.id) || priorityBusy || ticket.id !== activeTicketId.current) return
    if (ticket.status === 'RESOLVED' || ticket.status === 'CLOSED') return
    if (!selectedPriority || selectedPriority === ticket.priority || !availablePriorities.includes(selectedPriority)) return

    const trimmedReason = priorityReason.trim()
    if (!trimmedReason) {
      setPriorityError('Enter a reason for changing the ticket priority.')
      return
    }
    if (characterCount(trimmedReason) > 1000) {
      setPriorityError('The reason must be 1,000 characters or fewer.')
      return
    }

    const submittedTicketId = ticket.id
    const submittedTicketGeneration = activeTicketGeneration.current
    const requestedPriority = selectedPriority
    const isSubmittedTicketViewActive = () =>
      activeTicketId.current === submittedTicketId &&
      activeTicketGeneration.current === submittedTicketGeneration

    priorityInFlight.current.add(submittedTicketId)
    setPriorityPendingTicketIds((pendingIds) => new Set(pendingIds).add(submittedTicketId))
    setPriorityError(null)
    setPrioritySuccess(null)
    setPriorityRefreshWarning(null)
    try {
      const updatedTicket = await changeSupportTicketPriority(submittedTicketId, {
        priority: requestedPriority,
        reason: trimmedReason,
      })
      if (!isSubmittedTicketViewActive()) return
      if (updatedTicket.id !== submittedTicketId) {
        throw new Error('The server returned a different ticket. Reload this ticket before continuing.')
      }

      setTicket(updatedTicket)
      setPriorityReason('')
      const successMessage = `Priority changed to ${formatTicketLabel(updatedTicket.priority)}.`
      try {
        const refreshedTicket = await getSupportTicket(submittedTicketId)
        if (!isSubmittedTicketViewActive()) return
        if (refreshedTicket.id !== submittedTicketId) {
          throw new Error('The server returned a different ticket than requested.')
        }
        setTicket(refreshedTicket)
        setPrioritySuccess(successMessage)
      } catch {
        if (isSubmittedTicketViewActive()) {
          setPriorityRefreshWarning('The priority change was saved, but the ticket could not be refreshed. The saved ticket and history are shown; reload to check for newer updates.')
          setPrioritySuccess(successMessage)
        }
      }
    } catch (requestError) {
      if (isSubmittedTicketViewActive()) setPriorityError(getApiErrorMessage(requestError))
    } finally {
      priorityInFlight.current.delete(submittedTicketId)
      setPriorityPendingTicketIds((pendingIds) => {
        const nextPendingIds = new Set(pendingIds)
        nextPendingIds.delete(submittedTicketId)
        return nextPendingIds
      })
    }
  }

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

  async function handleReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (replyInFlight.current || replyBusy || !ticket || ticket.id !== activeTicketId.current) return
    if (ticket.status === 'RESOLVED' || ticket.status === 'CLOSED') return

    const submittedTicketId = ticket.id
    const trimmedMessage = replyMessage.trim()
    if (!trimmedMessage) {
      setReplyError('Enter a message before sending your reply.')
      return
    }
    if (characterCount(trimmedMessage) > 10000) {
      setReplyError('Your message must be 10,000 characters or fewer.')
      return
    }

    const isInternal = replyMode === 'internal'
    const isInformationRequest = replyMode === 'request_information'
    replyInFlight.current = true
    setReplyBusy(true)
    setReplyError(null)
    setReplySuccess(null)
    setReplyRefreshWarning(null)
    try {
      const savedTicket = await replyToTicket(submittedTicketId, {
        message: trimmedMessage,
        is_internal: isInternal,
        request_information: isInformationRequest,
      })
      if (activeTicketId.current !== submittedTicketId) return
      if (savedTicket.id !== submittedTicketId) {
        throw new Error('The server returned a different ticket. Reload this ticket before continuing.')
      }

      setTicket(savedTicket)
      setReplyMessage('')
      setReplyMode('public')
      const successMessage = isInternal
        ? 'Internal note added.'
        : isInformationRequest
          ? 'Information request sent.'
          : 'Public reply sent.'
      try {
        const refreshedTicket = await getSupportTicket(submittedTicketId)
        if (activeTicketId.current !== submittedTicketId) return
        if (refreshedTicket.id !== submittedTicketId) {
          throw new Error('The server returned a different ticket than requested.')
        }
        setTicket(refreshedTicket)
        setReplySuccess(successMessage)
      } catch {
        if (activeTicketId.current === submittedTicketId) {
          setReplyRefreshWarning('The reply was saved, but the ticket could not be refreshed. The saved response is shown; reload to check for newer updates.')
          setReplySuccess(successMessage)
        }
      }
    } catch (requestError) {
      if (activeTicketId.current === submittedTicketId) setReplyError(getApiErrorMessage(requestError))
    } finally {
      replyInFlight.current = false
      if (activeTicketId.current === submittedTicketId) setReplyBusy(false)
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
              {ticket.is_sla_paused && <p role="status" className="mt-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-950">SLA paused while waiting for a response from the ticket member.</p>}
              <section aria-labelledby="ticket-details" className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
                <h2 id="ticket-details" className="text-lg font-semibold text-slate-950">Ticket details</h2>
                <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
                  <div><dt className="text-slate-500">Created</dt><dd className="mt-1 font-medium text-slate-900">{formatDate(ticket.created_at)}</dd></div>
                  <div><dt className="text-slate-500">Assigned agent</dt><dd className="mt-1 font-medium text-slate-900">{ticket.assigned_to?.name ?? 'Unassigned'}</dd></div>
                  <div><dt className="text-slate-500">Member</dt><dd className="mt-1 font-medium text-slate-900">{ticket.member.name}</dd></div>
                  <div><dt className="text-slate-500">SLA due</dt><dd className="mt-1 font-medium text-slate-900">{formatDate(ticket.due_at)}</dd></div>
                </dl>
                <form onSubmit={handleStatusChange} className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-5">
                  <h3 className="text-sm font-semibold text-slate-900">Update status</h3>
                  {availableStatusTransitions.length > 0 ? <>
                    <p className="mt-1 text-sm text-slate-600">Choose a status transition available from {formatTicketLabel(ticket.status)}.</p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                      <div>
                        <label htmlFor="support-ticket-status" className="mb-1 block text-sm font-medium text-slate-700">New status</label>
                        <select id="support-ticket-status" value={selectedStatus} onChange={(event) => { setSelectedStatus(event.target.value as TicketStatus); setStatusError(null); setStatusSuccess(null); setStatusRefreshWarning(null) }} disabled={statusBusy} className="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-100">
                          {availableStatusTransitions.map((status) => <option key={status} value={status}>{formatTicketLabel(status)}</option>)}
                        </select>
                      </div>
                      <button type="submit" disabled={statusBusy || !selectedStatus} className="min-h-11 rounded-lg bg-emerald-800 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">{statusBusy ? 'Updating…' : `Set ${selectedStatus ? formatTicketLabel(selectedStatus) : 'status'}`}</button>
                    </div>
                    {selectedStatus === 'ESCALATED' && <div className="mt-3">
                      <label htmlFor="status-escalation-reason" className="mb-1 block text-sm font-medium text-slate-700">Escalation reason</label>
                      <textarea id="status-escalation-reason" value={statusReason} onChange={(event) => { setStatusReason(event.target.value); setStatusError(null); setStatusSuccess(null) }} rows={2} maxLength={1000} required disabled={statusBusy} className="block w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:bg-slate-100" />
                    </div>}
                  </> : <p className="mt-1 text-sm text-slate-600">No support status changes are available for a {formatTicketLabel(ticket.status)} ticket.</p>}
                  {statusError && <p role="alert" className="mt-3 text-sm text-rose-700">Status update failed: {statusError}</p>}
                  {statusRefreshWarning && <p role="alert" className="mt-3 text-sm text-amber-900">{statusRefreshWarning}</p>}
                  {statusSuccess && <p role="status" className="mt-3 text-sm text-emerald-800">{statusSuccess}</p>}
                </form>
                <form onSubmit={handlePriorityChange} className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-5">
                  <h3 className="text-sm font-semibold text-slate-900">Change priority</h3>
                  {ticket.status === 'RESOLVED' || ticket.status === 'CLOSED' ? (
                    <p role="status" className="mt-1 text-sm text-slate-600">Priority cannot be changed because this ticket is {ticket.status === 'RESOLVED' ? 'resolved' : 'closed'}.</p>
                  ) : (
                    <>
                      <p className="mt-1 text-sm text-slate-600">Current priority: <PriorityBadge priority={ticket.priority} />. Select a different priority and explain the change.</p>
                      <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                        <div>
                          <label htmlFor="support-ticket-priority" className="mb-1 block text-sm font-medium text-slate-700">New priority</label>
                          <select id="support-ticket-priority" value={selectedPriority} onChange={(event) => { setSelectedPriority(event.target.value as TicketPriority); setPriorityError(null); setPrioritySuccess(null); setPriorityRefreshWarning(null) }} disabled={priorityBusy || availablePriorities.length === 0} className="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-100">
                            {availablePriorities.map((priority) => <option key={priority} value={priority}>{formatTicketLabel(priority)}</option>)}
                          </select>
                        </div>
                        <button type="submit" disabled={priorityBusy || !selectedPriority || availablePriorities.length === 0} className="min-h-11 rounded-lg bg-emerald-800 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">{priorityBusy ? 'Updating…' : 'Update priority'}</button>
                      </div>
                      <div className="mt-3">
                        <label htmlFor="support-priority-reason" className="mb-1 block text-sm font-medium text-slate-700">Reason for change</label>
                        <textarea id="support-priority-reason" value={priorityReason} onChange={(event) => { setPriorityReason(Array.from(event.target.value).slice(0, 1000).join('')); setPriorityError(null); setPrioritySuccess(null); setPriorityRefreshWarning(null) }} rows={3} required aria-invalid={Boolean(priorityError)} aria-describedby={`${priorityError ? 'support-priority-error ' : ''}support-priority-help`} disabled={priorityBusy} className="block w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm leading-6 text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:bg-slate-100" />
                        <p id="support-priority-help" className="mt-2 text-xs text-slate-600">Required, maximum 1,000 characters. {characterCount(priorityReason.trim())}/1,000 characters.</p>
                      </div>
                      {priorityError && <p id="support-priority-error" role="alert" className="mt-3 text-sm text-rose-700">Priority change failed: {priorityError}</p>}
                      {priorityRefreshWarning && <p role="alert" className="mt-3 text-sm text-amber-900">{priorityRefreshWarning}</p>}
                      {prioritySuccess && <p role="status" className="mt-3 text-sm text-emerald-800">{prioritySuccess}</p>}
                    </>
                  )}
                </form>
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
              <TicketConversation replies={ticket.replies} audience="support" />
              <TicketHistory events={ticket.history} audience="support" />
              <section aria-labelledby="support-reply-heading" className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
                <h2 id="support-reply-heading" className="text-lg font-semibold text-slate-950">Reply to ticket</h2>
                {ticket.status === 'RESOLVED' || ticket.status === 'CLOSED' ? (
                  <p role="status" className="mt-3 rounded-lg bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
                    Replies are unavailable because this ticket is {ticket.status === 'RESOLVED' ? 'resolved' : 'closed'}.
                  </p>
                ) : (
                  <form onSubmit={handleReply} className="mt-4">
                    <fieldset disabled={replyBusy}>
                      <legend className="text-sm font-medium text-slate-800">Message visibility</legend>
                      <div className="mt-2 grid gap-3 sm:grid-cols-2">
                        <label className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 ${replyMode === 'public' ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200 bg-white'}`}>
                          <input type="radio" name="reply-mode" value="public" checked={replyMode === 'public'} onChange={() => { setReplyMode('public'); setReplyError(null); setReplySuccess(null); setReplyRefreshWarning(null) }} className="mt-1 accent-emerald-700" />
                          <span><span className="block text-sm font-semibold text-slate-900">Public reply</span><span className="mt-1 block text-xs leading-5 text-slate-600">Visible to the ticket member and support staff.</span></span>
                        </label>
                        <label className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 ${replyMode === 'internal' ? 'border-amber-400 bg-amber-50' : 'border-slate-200 bg-white'}`}>
                          <input type="radio" name="reply-mode" value="internal" checked={replyMode === 'internal'} onChange={() => { setReplyMode('internal'); setReplyError(null); setReplySuccess(null); setReplyRefreshWarning(null) }} className="mt-1 accent-amber-700" />
                          <span><span className="block text-sm font-semibold text-amber-950">Internal note</span><span className="mt-1 block text-xs leading-5 text-amber-900">Visible only to support staff. The ticket member will not see this note.</span></span>
                        </label>
                        <label className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 ${replyMode === 'request_information' ? 'border-sky-400 bg-sky-50' : 'border-slate-200 bg-white'}`}>
                          <input type="radio" name="reply-mode" value="request_information" checked={replyMode === 'request_information'} onChange={() => { setReplyMode('request_information'); setReplyError(null); setReplySuccess(null); setReplyRefreshWarning(null) }} className="mt-1 accent-sky-700" />
                          <span><span className="block text-sm font-semibold text-sky-950">Request information</span><span className="mt-1 block text-xs leading-5 text-sky-900">Sends a public message to the member and pauses the SLA while waiting for their response.</span></span>
                        </label>
                      </div>
                    </fieldset>
                    {replyMode === 'internal' && <p className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-950">Internal note — visible only to support staff. Do not include this in member-facing communication.</p>}
                    {replyMode === 'request_information' && <p className="mt-4 rounded-lg border border-sky-300 bg-sky-50 px-4 py-3 text-sm font-medium text-sky-950">This is a public request for information. The member will see it, and the backend will pause the SLA until they respond.</p>}
                    <div className="mt-4">
                      <label htmlFor="support-ticket-reply" className="block text-sm font-medium text-slate-800">{replyMode === 'internal' ? 'Internal note' : replyMode === 'request_information' ? 'Information request' : 'Your reply'}</label>
                      <textarea
                        id="support-ticket-reply"
                        value={replyMessage}
                        onChange={(event) => { setReplyMessage(event.target.value); setReplyError(null); setReplySuccess(null); setReplyRefreshWarning(null) }}
                        rows={5}
                        required
                        aria-invalid={Boolean(replyError)}
                        aria-describedby={`${replyError ? 'support-reply-error ' : ''}support-reply-help`}
                        disabled={replyBusy}
                        placeholder={replyMode === 'internal' ? 'Write an internal note for support staff' : replyMode === 'request_information' ? 'Ask the ticket member for the information needed' : 'Write a reply for the ticket member'}
                        className="mt-2 block w-full resize-y rounded-lg border border-slate-300 px-3 py-2.5 text-sm leading-6 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20 disabled:bg-slate-50"
                      />
                      <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <p id="support-reply-help" className="text-xs text-slate-600">Maximum 10,000 characters. {replyMode === 'internal' ? 'Only support staff can view this note.' : 'The ticket member can view this message.'}</p>
                        <p className="text-right text-xs text-slate-600">{characterCount(replyMessage.trim())}/10,000 characters</p>
                      </div>
                    </div>
                    {replyError && <p id="support-reply-error" role="alert" className="mt-3 text-sm text-rose-700">{replyError}</p>}
                    {replyRefreshWarning && <p role="alert" className="mt-3 text-sm text-amber-900">{replyRefreshWarning}</p>}
                    {replySuccess && <p role="status" className="mt-3 text-sm text-emerald-800">{replySuccess}</p>}
                    {replyBusy && <p role="status" className="mt-3 text-sm text-slate-500">Sending…</p>}
                    <div className="mt-4 flex justify-end">
                      <button type="submit" disabled={replyBusy} className="min-h-11 rounded-lg bg-emerald-800 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:opacity-60">
                        {replyBusy ? 'Sending…' : replyMode === 'internal' ? 'Add internal note' : replyMode === 'request_information' ? 'Request information' : 'Send public reply'}
                      </button>
                    </div>
                  </form>
                )}
              </section>
            </> : null}
      </div>
    </main>
  )
}
