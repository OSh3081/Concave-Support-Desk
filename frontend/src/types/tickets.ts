export type TicketCategory =
  | 'PAYMENT'
  | 'PROFILE_CHANGE'
  | 'SURVEY_ISSUE'
  | 'ELIGIBILITY'
  | 'OTHER'

export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH'

export type TicketStatus =
  | 'OPEN'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'CLOSED'
  | 'REOPENED'
  | 'ESCALATED'

export type TicketUserRole = 'MEMBER' | 'SUPPORT_AGENT' | 'SUPPORT_HEAD' | 'SYSTEM'

export type TicketUserSummary = {
  id: number
  name: string
  email: string
  role: TicketUserRole
}

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
export type TicketHistoryValue = { [key: string]: JsonValue } | JsonValue[]

export type TicketReply = {
  id: number
  sender: TicketUserSummary
  message: string
  is_internal: boolean
  created_at: string
}

export type TicketHistory = {
  id: number
  actor: TicketUserSummary
  action: string
  old_value: TicketHistoryValue | null
  new_value: TicketHistoryValue | null
  reason: string | null
  created_at: string
}

export type TicketSummary = {
  id: number
  ticket_number: string
  category: TicketCategory
  subject: string
  priority: TicketPriority
  status: TicketStatus
  assigned_to: TicketUserSummary | null
  created_at: string
  updated_at: string
  due_at: string
  is_overdue: boolean
}

export type TicketDetail = TicketSummary & {
  member: TicketUserSummary
  description: string
  reopen_count: number
  resolved_at: string | null
  closed_at: string | null
  is_sla_paused: boolean
  replies: TicketReply[]
  history: TicketHistory[]
}

export type TicketList = {
  items: TicketSummary[]
  page: number
  page_size: number
  total: number
}

export type TicketCreateRequest = {
  category: TicketCategory
  subject: string
  description: string
}

export type ReplyCreateRequest = {
  message: string
}

export type ReopenRequest = {
  reason: string
}
