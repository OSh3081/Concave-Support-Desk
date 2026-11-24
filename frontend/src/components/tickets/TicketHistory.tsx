import { useMemo } from 'react'
import { formatTicketLabel } from '../common/TicketBadges'
import type { TicketHistory as TicketHistoryEvent } from '../../types/tickets'

type TicketHistoryProps = {
  events: TicketHistoryEvent[]
  audience: 'member' | 'support'
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function isInternalReplyHistory(event: TicketHistoryEvent): boolean {
  if (event.action !== 'REPLY_ADDED' || event.new_value === null || Array.isArray(event.new_value)) return false
  return event.new_value.is_internal === true
}

function HistoryEvent({ event, isInternalNote }: { event: TicketHistoryEvent; isInternalNote: boolean }) {
  return (
    <li className="relative pl-6 before:absolute before:bottom-0 before:left-[5px] before:top-2 before:w-px before:bg-slate-200 last:before:hidden">
      <span aria-hidden="true" className={`absolute left-0 top-2 h-3 w-3 rounded-full border-2 bg-white ${isInternalNote ? 'border-amber-600' : 'border-emerald-700'}`} />
      <div className="pb-5">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <p className={`text-sm font-semibold ${isInternalNote ? 'text-amber-950' : 'text-slate-800'}`}>
            {isInternalNote ? 'Internal note added' : formatTicketLabel(event.action)}
          </p>
          <time dateTime={event.created_at} className="text-xs text-slate-500">{formatDateTime(event.created_at)}</time>
        </div>
        <p className="mt-1 text-xs text-slate-500">By {event.actor.name}</p>
        {event.reason && <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">{event.reason}</p>}
      </div>
    </li>
  )
}

export default function TicketHistory({ events, audience }: TicketHistoryProps) {
  const visibleEvents = useMemo(
    () => [...events]
      .filter((event) => audience === 'support' || !isInternalReplyHistory(event))
      .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id),
    [events, audience],
  )

  return (
    <section aria-labelledby="history-heading" className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">Ticket updates</p>
        <h2 id="history-heading" className="mt-1 text-xl font-semibold text-slate-950">History</h2>
      </div>
      {visibleEvents.length > 0 ? (
        <ol className="space-y-0">
          {visibleEvents.map((event) => <HistoryEvent key={event.id} event={event} isInternalNote={audience === 'support' && isInternalReplyHistory(event)} />)}
        </ol>
      ) : (
        <p className="text-sm text-slate-500">No ticket updates to show.</p>
      )}
    </section>
  )
}
