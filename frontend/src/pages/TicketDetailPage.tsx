import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../services/apiClient'
import { confirmTicketResolution, getTicket, reopenTicket, replyToTicket } from '../services/tickets.service'
import { formatTicketLabel, isTicketStatus, PriorityBadge, StatusBadge } from '../components/common/TicketBadges'
import type { TicketDetail, TicketHistory, TicketReply } from '../types/tickets'

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function characterCount(value: string): number {
  return Array.from(value).length
}

function ConversationReply({ reply }: { reply: TicketReply }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <p className="break-words text-sm font-semibold text-slate-900">{reply.sender.name}</p>
        <time dateTime={reply.created_at} className="text-xs text-slate-500">{formatDateTime(reply.created_at)}</time>
      </div>
      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{reply.message}</p>
    </article>
  )
}

function HistoryEvent({ event }: { event: TicketHistory }) {
  return (
    <li className="relative pl-6 before:absolute before:bottom-0 before:left-[5px] before:top-2 before:w-px before:bg-slate-200 last:before:hidden">
      <span aria-hidden="true" className="absolute left-0 top-2 h-3 w-3 rounded-full border-2 border-emerald-700 bg-white" />
      <div className="pb-5">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <p className="text-sm font-semibold text-slate-800">{formatTicketLabel(event.action)}</p>
          <time dateTime={event.created_at} className="text-xs text-slate-500">{formatDateTime(event.created_at)}</time>
        </div>
        <p className="mt-1 text-xs text-slate-500">By {event.actor.name}</p>
        {event.reason && <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">{event.reason}</p>}
      </div>
    </li>
  )
}

function isInternalReplyHistory(event: TicketHistory): boolean {
  if (event.action !== 'REPLY_ADDED' || event.new_value === null || Array.isArray(event.new_value)) return false
  return event.new_value.is_internal === true
}

export default function TicketDetailPage() {
  const { ticketId: ticketIdParam } = useParams<{ ticketId: string }>()
  const ticketId = Number(ticketIdParam)
  const validTicketId = Number.isSafeInteger(ticketId) && ticketId > 0
  const activeTicketId = useRef(ticketId)
  activeTicketId.current = ticketId
  const replyInFlight = useRef(false)
  const lifecycleInFlight = useRef(false)
  const [ticket, setTicket] = useState<TicketDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadErrorForTicketId, setLoadErrorForTicketId] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [message, setMessage] = useState('')
  const [replyError, setReplyError] = useState<string | null>(null)
  const [replySuccess, setReplySuccess] = useState<string | null>(null)
  const [isReplying, setIsReplying] = useState(false)
  const [lifecycleError, setLifecycleError] = useState<string | null>(null)
  const [lifecycleSuccess, setLifecycleSuccess] = useState<string | null>(null)
  const [lifecycleAction, setLifecycleAction] = useState<'confirm' | 'reopen' | null>(null)
  const [reopenReason, setReopenReason] = useState('')

  useEffect(() => {
    let active = true
    setTicket(null)
    setLoadError(null)
    setLoadErrorForTicketId(null)
    setMessage('')
    setReplyError(null)
    setReplySuccess(null)
    setIsReplying(false)
    setLifecycleError(null)
    setLifecycleSuccess(null)
    setLifecycleAction(null)
    setReopenReason('')

    if (!validTicketId) {
      setLoadError('This ticket address is invalid.')
      setLoadErrorForTicketId(ticketIdParam ?? '')
      return () => { active = false }
    }

    getTicket(ticketId)
      .then((result) => {
        if (result.id !== ticketId) throw new Error('The server returned a different ticket than requested.')
        if (active && activeTicketId.current === ticketId) setTicket(result)
      })
      .catch((error: unknown) => {
        if (active && activeTicketId.current === ticketId) {
          setLoadError(getApiErrorMessage(error))
          setLoadErrorForTicketId(ticketIdParam ?? '')
        }
      })

    return () => { active = false }
  }, [ticketId, validTicketId, refreshKey])

  const currentTicket = ticket?.id === ticketId ? ticket : null
  const visibleReplies = useMemo(
    () => [...(currentTicket?.replies ?? [])].filter((reply) => !reply.is_internal).sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id),
    [currentTicket],
  )
  const visibleHistory = useMemo(
    () => [...(currentTicket?.history ?? [])].filter((event) => !isInternalReplyHistory(event)).sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id),
    [currentTicket],
  )
  const statusIsKnown = currentTicket ? isTicketStatus(currentTicket.status) : true
  const repliesUnavailable = !statusIsKnown || currentTicket?.status === 'RESOLVED' || currentTicket?.status === 'CLOSED'
  const currentLoadError = loadErrorForTicketId === (ticketIdParam ?? '') ? loadError : null

  async function handleReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (replyInFlight.current || isReplying || !currentTicket || currentTicket.id !== activeTicketId.current || !validTicketId || repliesUnavailable) return
    const submittedTicketId = currentTicket.id

    const trimmedMessage = message.trim()
    if (!trimmedMessage) {
      setReplyError('Enter a message before sending your reply.')
      return
    }
    if (characterCount(trimmedMessage) > 10000) {
      setReplyError('Your message must be 10,000 characters or fewer.')
      return
    }

    replyInFlight.current = true
    setIsReplying(true)
    setReplyError(null)
    setReplySuccess(null)
    try {
      const updated = await replyToTicket(submittedTicketId, { message: trimmedMessage })
      if (activeTicketId.current !== submittedTicketId) return
      if (updated.id !== submittedTicketId) throw new Error('The server returned a different ticket. Reload the ticket before continuing.')
      setTicket(updated)
      setMessage('')
      setReplySuccess('Your reply was sent.')
      setLoadError(null)
    } catch (error: unknown) {
      if (activeTicketId.current === submittedTicketId) setReplyError(getApiErrorMessage(error))
    } finally {
      replyInFlight.current = false
      if (activeTicketId.current === submittedTicketId) setIsReplying(false)
    }
  }

  async function handleLifecycleAction(action: 'confirm' | 'reopen') {
    if (lifecycleInFlight.current || lifecycleAction || !currentTicket || currentTicket.id !== activeTicketId.current) return
    const submittedTicketId = currentTicket.id
    const reason = reopenReason.trim()
    if (action === 'reopen' && (!reason || Array.from(reason).length > 1000)) {
      setLifecycleError(reason ? 'Your reason must be 1,000 characters or fewer.' : 'Enter a reason for reopening this ticket.')
      return
    }
    if (action === 'confirm' && !window.confirm('Confirm that this issue is resolved and close the ticket?')) return
    if (action === 'reopen' && !window.confirm('Reopen this ticket with the reason you entered? The support team will be notified.')) return

    lifecycleInFlight.current = true
    setLifecycleAction(action)
    setLifecycleError(null)
    setLifecycleSuccess(null)
    try {
      const updated = action === 'confirm'
        ? await confirmTicketResolution(submittedTicketId)
        : await reopenTicket(submittedTicketId, { reason })
      if (activeTicketId.current !== submittedTicketId) return
      if (updated.id !== submittedTicketId) throw new Error('The server returned a different ticket. Reload this ticket before continuing.')
      setTicket(updated)
      setReopenReason('')
      setLifecycleSuccess(action === 'confirm' ? 'Resolution confirmed. This ticket is now closed.' : 'Ticket reopened. The support team has been notified.')
      setLoadError(null)
    } catch (error: unknown) {
      if (activeTicketId.current === submittedTicketId) setLifecycleError(getApiErrorMessage(error))
    } finally {
      lifecycleInFlight.current = false
      if (activeTicketId.current === submittedTicketId) setLifecycleAction(null)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-6 sm:py-9">
      <div className="mx-auto max-w-5xl">
        <header className="border-b border-slate-200 pb-5">
          <Link to="/member" className="text-sm font-semibold text-emerald-800 hover:text-emerald-950">← Back to My Tickets</Link>
          <p className="mt-5 text-xs font-bold uppercase tracking-[0.16em] text-emerald-800">Concave Insights · Support Desk</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Ticket details</h1>
        </header>

        {!currentTicket && !currentLoadError ? (
          <div role="status" className="mt-6 rounded-2xl border border-slate-200 bg-white px-5 py-12 text-center text-sm text-slate-600 shadow-sm">Loading ticket…</div>
        ) : currentLoadError && !currentTicket ? (
          <section role="alert" className="mt-6 rounded-2xl border border-rose-200 bg-white px-5 py-10 text-center shadow-sm">
            <h2 className="font-semibold text-slate-900">We couldn’t load this ticket.</h2>
            <p className="mt-2 text-sm text-slate-600">{currentLoadError}</p>
            <button type="button" onClick={() => setRefreshKey((current) => current + 1)} disabled={!validTicketId} className="mt-5 rounded-lg bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900 disabled:opacity-50">Try again</button>
          </section>
        ) : currentTicket ? (
          <>
            <section aria-labelledby="ticket-heading" className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
              <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold tracking-wide text-emerald-800">{currentTicket.ticket_number}</p>
                  <h2 id="ticket-heading" className="mt-1 break-words text-2xl font-semibold tracking-tight text-slate-950">{currentTicket.subject}</h2>
                </div>
                <StatusBadge status={currentTicket.status} />
              </div>
              {!statusIsKnown && <p role="status" className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">This ticket has an unfamiliar status ({currentTicket.status}). Lifecycle actions are unavailable until the ticket can be refreshed.</p>}
              {(currentTicket.status === 'RESOLVED' || currentTicket.status === 'CLOSED') && statusIsKnown && (
                <div className="mt-5 rounded-xl border border-emerald-100 bg-emerald-50/60 p-4 sm:flex sm:items-start sm:justify-between sm:gap-5">
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-slate-900">Ticket actions</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-600">{currentTicket.status === 'RESOLVED' ? 'If the issue is fixed, confirm the resolution to close this ticket.' : 'If the issue returns, you can request to reopen this ticket. The server checks the reopening window and limit.'}</p>
                  </div>
                  {currentTicket.status === 'RESOLVED' ? (
                    <button type="button" onClick={() => void handleLifecycleAction('confirm')} disabled={lifecycleAction !== null} className="mt-3 w-full shrink-0 rounded-lg bg-emerald-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-60 sm:mt-0 sm:w-auto">{lifecycleAction === 'confirm' ? 'Confirming…' : 'Confirm resolution'}</button>
                  ) : (
                    <div className="mt-3 w-full shrink-0 sm:mt-0 sm:max-w-md">
                      <label htmlFor="reopen-reason" className="block text-sm font-medium text-slate-800">Why does this ticket need to be reopened?</label>
                      <textarea id="reopen-reason" value={reopenReason} onChange={(event) => { setReopenReason(event.target.value); setLifecycleError(null) }} rows={3} aria-invalid={Boolean(lifecycleError && (!reopenReason.trim() || Array.from(reopenReason.trim()).length > 1000))} aria-describedby={lifecycleError ? 'lifecycle-action-error reopen-reason-count' : 'reopen-reason-count'} disabled={lifecycleAction !== null} className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20 disabled:bg-slate-50" />
                      <p id="reopen-reason-count" className="mt-1 text-right text-xs text-slate-600">{Array.from(reopenReason).length}/1,000 characters</p>
                      <button type="button" onClick={() => void handleLifecycleAction('reopen')} disabled={lifecycleAction !== null} className="mt-2 min-h-11 w-full rounded-lg border border-emerald-800 px-4 py-2.5 text-sm font-semibold text-emerald-950 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60">{lifecycleAction === 'reopen' ? 'Reopening…' : 'Reopen ticket'}</button>
                    </div>
                  )}
                </div>
              )}
              {lifecycleError && <p id="lifecycle-action-error" role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">The ticket action failed: {lifecycleError}</p>}
              {lifecycleSuccess && <p role="status" className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{lifecycleSuccess}</p>}
              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Category</p><p className="mt-1 text-sm font-medium text-slate-800">{formatTicketLabel(currentTicket.category)}</p></div>
                <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Priority</p><div className="mt-1"><PriorityBadge priority={currentTicket.priority} /></div></div>
                <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assigned to</p><p className="mt-1 text-sm font-medium text-slate-800">{currentTicket.assigned_to?.name ?? 'Not yet assigned'}</p></div>
                <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Created</p><time dateTime={currentTicket.created_at} className="mt-1 block text-sm text-slate-700">{formatDateTime(currentTicket.created_at)}</time></div>
                <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Last updated</p><time dateTime={currentTicket.updated_at} className="mt-1 block text-sm text-slate-700">{formatDateTime(currentTicket.updated_at)}</time></div>
              </div>
              <div className="mt-6 rounded-xl bg-slate-50 p-4 sm:p-5">
                <h3 className="text-sm font-semibold text-slate-900">Description</h3>
                <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{currentTicket.description}</p>
              </div>
            </section>

            <section aria-labelledby="conversation-heading" className="mt-7">
              <div className="mb-3 flex items-end justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">Messages</p>
                  <h2 id="conversation-heading" className="mt-1 text-xl font-semibold text-slate-950">Conversation</h2>
                </div>
                <span className="text-xs text-slate-500">{visibleReplies.length} {visibleReplies.length === 1 ? 'reply' : 'replies'}</span>
              </div>
              {visibleReplies.length > 0 ? (
                <div className="space-y-3">{visibleReplies.map((reply) => <ConversationReply key={reply.id} reply={reply} />)}</div>
              ) : (
                <div className="rounded-xl border border-dashed border-slate-300 bg-white px-5 py-8 text-center text-sm text-slate-500">No replies yet. Your message and any support responses will appear here.</div>
              )}
            </section>

            <section aria-labelledby="history-heading" className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">Ticket updates</p>
                <h2 id="history-heading" className="mt-1 text-xl font-semibold text-slate-950">History</h2>
              </div>
              {visibleHistory.length > 0 ? (
                <ol className="space-y-0">{visibleHistory.map((event) => <HistoryEvent key={event.id} event={event} />)}</ol>
              ) : (
                <p className="text-sm text-slate-500">No ticket updates to show.</p>
              )}
            </section>

            <section aria-labelledby="reply-heading" className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <h2 id="reply-heading" className="text-lg font-semibold text-slate-950">Add a reply</h2>
              {repliesUnavailable ? (
                <p className="mt-3 rounded-lg bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
                  {!statusIsKnown ? 'Replies are unavailable while this ticket has an unfamiliar status.' : `Replies are unavailable because this ticket is ${currentTicket.status === 'RESOLVED' ? 'resolved and awaiting your confirmation' : 'closed'}.`}
                </p>
              ) : (
                <form onSubmit={handleReply} className="mt-4">
                  <label htmlFor="ticket-reply" className="block text-sm font-medium text-slate-800">Your message</label>
                  <textarea
                    id="ticket-reply"
                    value={message}
                    onChange={(event) => { setMessage(event.target.value); setReplyError(null) }}
                    rows={5}
                    aria-invalid={Boolean(replyError)}
                    aria-describedby={`${replyError ? 'ticket-reply-error ' : ''}ticket-reply-help`}
                    className="mt-2 block w-full resize-y rounded-lg border border-slate-300 px-3 py-2.5 text-sm leading-6 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20 disabled:bg-slate-50"
                    placeholder="Write a message for the support team"
                    disabled={isReplying}
                  />
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p id="ticket-reply-help" className="text-xs text-slate-600">Maximum 10,000 characters. Replies are visible to the support team.</p>
                    <p className="text-right text-xs text-slate-600">{characterCount(message.trim())}/10,000 characters</p>
                  </div>
                  {replyError && <p id="ticket-reply-error" role="alert" className="mt-3 text-sm text-rose-700">{replyError}</p>}
                  {replySuccess && <p role="status" className="mt-3 text-sm text-emerald-800">{replySuccess}</p>}
                  {isReplying && <p role="status" className="mt-3 text-sm text-slate-500">Sending your reply…</p>}
                  <div className="mt-4 flex justify-end">
                    <button type="submit" disabled={isReplying} className="min-h-11 rounded-lg bg-emerald-800 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-60">
                      {isReplying ? 'Sending…' : 'Send reply'}
                    </button>
                  </div>
                </form>
              )}
            </section>
          </>
        ) : null}
      </div>
    </main>
  )
}
