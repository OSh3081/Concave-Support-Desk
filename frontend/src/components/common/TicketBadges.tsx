import type { TicketPriority, TicketStatus } from '../../types/tickets'

const statusStyles: Partial<Record<string, string>> = {
  OPEN: 'bg-sky-50 text-sky-800 ring-sky-200',
  IN_PROGRESS: 'bg-violet-50 text-violet-800 ring-violet-200',
  RESOLVED: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  CLOSED: 'bg-slate-100 text-slate-700 ring-slate-300',
  REOPENED: 'bg-amber-50 text-amber-900 ring-amber-200',
  ESCALATED: 'bg-rose-50 text-rose-800 ring-rose-200',
}

const priorityStyles: Partial<Record<string, string>> = {
  LOW: 'bg-slate-100 text-slate-700',
  MEDIUM: 'bg-amber-50 text-amber-900',
  HIGH: 'bg-rose-50 text-rose-800',
}

export function formatTicketLabel(value: string): string {
  return value.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function isTicketStatus(value: string): value is TicketStatus {
  return ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'REOPENED', 'ESCALATED'].includes(value)
}

export function StatusBadge({ status }: { status: TicketStatus | string }) {
  return (
    <span className={`inline-flex max-w-full whitespace-normal break-words rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${statusStyles[status] ?? 'bg-slate-100 text-slate-800 ring-slate-300'}`}>
      {formatTicketLabel(status)}
    </span>
  )
}

export function PriorityBadge({ priority }: { priority: TicketPriority | string }) {
  return (
    <span className={`inline-flex max-w-full whitespace-normal break-words rounded-full px-2.5 py-1 text-xs font-semibold ${priorityStyles[priority] ?? 'bg-slate-100 text-slate-800'}`}>
      {formatTicketLabel(priority)}
    </span>
  )
}
