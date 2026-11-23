import apiClient from './apiClient'
import type {
  ReplyCreateRequest,
  ReopenRequest,
  TicketCreateRequest,
  TicketDetail,
  TicketList,
} from '../types/tickets'

export async function getMyTickets(page = 1, pageSize = 20): Promise<TicketList> {
  const { data } = await apiClient.get<TicketList>('/tickets', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function getSupportTickets(page = 1, pageSize = 20): Promise<TicketList> {
  const { data } = await apiClient.get<TicketList>('/support/tickets', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function getSupportTicket(ticketId: number): Promise<TicketDetail> {
  const { data } = await apiClient.get<TicketDetail>(`/support/tickets/${ticketId}`)
  return data
}

export async function getTicket(ticketId: number): Promise<TicketDetail> {
  const { data } = await apiClient.get<TicketDetail>(`/tickets/${ticketId}`)
  return data
}

export async function createTicket(payload: TicketCreateRequest): Promise<TicketDetail> {
  const { data } = await apiClient.post<TicketDetail>('/tickets', payload)
  return data
}

export async function replyToTicket(
  ticketId: number,
  payload: ReplyCreateRequest,
): Promise<TicketDetail> {
  const { data } = await apiClient.post<TicketDetail>(`/tickets/${ticketId}/replies`, payload)
  return data
}

export async function confirmTicketResolution(ticketId: number): Promise<TicketDetail> {
  const { data } = await apiClient.post<TicketDetail>(`/tickets/${ticketId}/confirm-resolution`)
  return data
}

export async function reopenTicket(
  ticketId: number,
  payload: ReopenRequest,
): Promise<TicketDetail> {
  const { data } = await apiClient.post<TicketDetail>(`/tickets/${ticketId}/reopen`, payload)
  return data
}
