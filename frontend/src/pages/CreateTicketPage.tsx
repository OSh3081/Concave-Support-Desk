import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../services/apiClient'
import { createTicket } from '../services/tickets.service'
import type { TicketCategory, TicketCreateRequest } from '../types/tickets'

const categories: { value: TicketCategory; label: string }[] = [
  { value: 'PAYMENT', label: 'Payment' },
  { value: 'PROFILE_CHANGE', label: 'Profile change' },
  { value: 'SURVEY_ISSUE', label: 'Survey issue' },
  { value: 'ELIGIBILITY', label: 'Eligibility' },
  { value: 'OTHER', label: 'Other' },
]

type FieldErrors = Partial<Record<'category' | 'subject' | 'description', string>>

function countCharacters(value: string): number {
  return Array.from(value).length
}

export default function CreateTicketPage() {
  const navigate = useNavigate()
  const [category, setCategory] = useState<TicketCategory | ''>('')
  const [subject, setSubject] = useState('')
  const [description, setDescription] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [requestError, setRequestError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return

    const trimmedSubject = subject.trim()
    const trimmedDescription = description.trim()
    const errors: FieldErrors = {}

    if (!category) errors.category = 'Choose a category.'
    if (!trimmedSubject) errors.subject = 'Enter a subject.'
    else if (countCharacters(trimmedSubject) > 200) errors.subject = 'Subject must be 200 characters or fewer.'
    if (!trimmedDescription) errors.description = 'Enter a description.'
    else if (countCharacters(trimmedDescription) > 10000) errors.description = 'Description must be 10,000 characters or fewer.'

    setFieldErrors(errors)
    setRequestError(null)
    if (Object.keys(errors).length > 0 || !category) return

    const payload: TicketCreateRequest = {
      category,
      subject: trimmedSubject,
      description: trimmedDescription,
    }

    setIsSubmitting(true)
    try {
      const ticket = await createTicket(payload)
      navigate('/member', {
        replace: true,
        state: { ticketCreated: true, ticketNumber: ticket.ticket_number },
      })
    } catch (error: unknown) {
      setRequestError(getApiErrorMessage(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-6 sm:py-9">
      <div className="mx-auto max-w-3xl">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <Link to="/member" className="text-sm font-semibold text-emerald-800 hover:text-emerald-950">← Back to dashboard</Link>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.16em] text-emerald-800">Concave Insights · Support Desk</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Create a ticket</h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">Tell us what you need help with. Our support team will review your request.</p>
          </div>
        </header>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8">
          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-6">
              <div>
                <label htmlFor="ticket-category" className="block text-sm font-semibold text-slate-800">Category <span className="text-rose-700">*</span></label>
                <select
                  id="ticket-category"
                  value={category}
                  onChange={(event) => setCategory(event.target.value as TicketCategory | '')}
                  aria-invalid={Boolean(fieldErrors.category)}
                  aria-describedby={fieldErrors.category ? 'ticket-category-error' : undefined}
                  className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
                  disabled={isSubmitting}
                >
                  <option value="">Select a category</option>
                  {categories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                {fieldErrors.category && <p id="ticket-category-error" className="mt-1.5 text-sm text-rose-700">{fieldErrors.category}</p>}
              </div>

              <div>
                <div className="flex items-baseline justify-between gap-2">
                  <label htmlFor="ticket-subject" className="block text-sm font-semibold text-slate-800">Subject <span className="text-rose-700">*</span></label>
                  <span className="text-xs text-slate-500">{countCharacters(subject.trim())}/200</span>
                </div>
                <input
                  id="ticket-subject"
                  type="text"
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                  required
                  aria-invalid={Boolean(fieldErrors.subject)}
                  aria-describedby={fieldErrors.subject ? 'ticket-subject-error' : undefined}
                  className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
                  placeholder="Briefly summarize the issue"
                  disabled={isSubmitting}
                />
                {fieldErrors.subject && <p id="ticket-subject-error" className="mt-1.5 text-sm text-rose-700">{fieldErrors.subject}</p>}
              </div>

              <div>
                <div className="flex items-baseline justify-between gap-2">
                  <label htmlFor="ticket-description" className="block text-sm font-semibold text-slate-800">Description <span className="text-rose-700">*</span></label>
                  <span className="text-xs text-slate-500">{countCharacters(description.trim())}/10,000</span>
                </div>
                <textarea
                  id="ticket-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  required
                  rows={7}
                  aria-invalid={Boolean(fieldErrors.description)}
                  aria-describedby={fieldErrors.description ? 'ticket-description-error' : undefined}
                  className="mt-2 block w-full resize-y rounded-lg border border-slate-300 px-3 py-2.5 text-sm leading-6 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
                  placeholder="Share the details that will help us understand and resolve your request"
                  disabled={isSubmitting}
                />
                {fieldErrors.description && <p id="ticket-description-error" className="mt-1.5 text-sm text-rose-700">{fieldErrors.description}</p>}
              </div>
            </div>

            {requestError && (
              <div role="alert" className="mt-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                <p className="font-semibold">Your ticket could not be submitted.</p>
                <p className="mt-1">{requestError}</p>
              </div>
            )}

            <div className="mt-8 flex flex-col-reverse gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:justify-end">
              <Link to="/member" aria-disabled={isSubmitting} className={`inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 ${isSubmitting ? 'pointer-events-none opacity-50' : ''}`}>
                Cancel
              </Link>
              <button type="submit" disabled={isSubmitting} className="inline-flex items-center justify-center rounded-lg bg-emerald-800 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-60">
                {isSubmitting ? 'Submitting…' : 'Submit ticket'}
              </button>
            </div>
            {isSubmitting && <p role="status" className="mt-3 text-right text-sm text-slate-500">Submitting your ticket…</p>}
          </form>
        </section>
      </div>
    </main>
  )
}
