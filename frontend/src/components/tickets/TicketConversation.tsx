import { useMemo } from 'react'
import type { TicketReply } from '../../types/tickets'

type TicketConversationProps = {
  replies: TicketReply[]
  audience: 'member' | 'support'
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function ConversationReply({ reply, audience }: { reply: TicketReply; audience: TicketConversationProps['audience'] }) {
  const isInternal = audience === 'support' && reply.is_internal

  return (
    <article className={`rounded-xl border p-4 sm:p-5 ${isInternal ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white'}`}>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <p className="break-words text-sm font-semibold text-slate-900">{reply.sender.name}</p>
        <div className="flex flex-wrap items-center gap-2">
          {audience === 'support' && <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${isInternal ? 'bg-amber-200 text-amber-950' : 'bg-emerald-100 text-emerald-900'}`}>
            {isInternal ? 'Internal note' : 'Public reply'}
          </span>}
          <time dateTime={reply.created_at} className="text-xs text-slate-500">{formatDateTime(reply.created_at)}</time>
        </div>
      </div>
      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{reply.message}</p>
    </article>
  )
}

export default function TicketConversation({ replies, audience }: TicketConversationProps) {
  const visibleReplies = useMemo(
    () => [...replies]
      .filter((reply) => audience === 'support' || !reply.is_internal)
      .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id),
    [replies, audience],
  )

  return (
    <section aria-labelledby="conversation-heading" className="mt-7">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">Messages</p>
          <h2 id="conversation-heading" className="mt-1 text-xl font-semibold text-slate-950">Conversation</h2>
        </div>
        <span className="text-xs text-slate-500">{visibleReplies.length} {visibleReplies.length === 1 ? 'reply' : 'replies'}</span>
      </div>
      {visibleReplies.length > 0 ? (
        <div className="space-y-3">
          {visibleReplies.map((reply) => <ConversationReply key={reply.id} reply={reply} audience={audience} />)}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-5 py-8 text-center text-sm text-slate-500">
          {audience === 'member'
            ? 'No replies yet. Your message and any support responses will appear here.'
            : 'No replies or internal notes yet.'}
        </div>
      )}
    </section>
  )
}
