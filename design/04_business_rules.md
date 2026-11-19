# Business Rules and Assessment Decisions

## 1. Priority defaults
The Support Head configures a default priority for each ticket category. Proposed seed defaults:

| Category | Default priority |
|---|---|
| Payment | High |
| Profile change | Medium |
| Survey issue | High |
| Eligibility | Medium |
| Other | Low |

These are initial demo defaults, not immutable rules.

When a member creates a ticket:
1. Read the category's current default priority.
2. Store that priority on the ticket.
3. Read the TAT for that priority.
4. Create the SLA deadline.

Changing a category's default affects future tickets only. Existing tickets retain their stored priority.

Support agents may override an individual ticket's priority only with a mandatory reason. The change is audited and the ticket's active SLA deadline is recalculated using the new TAT. The implementation should document whether elapsed time is preserved; recommended policy: preserve elapsed active time and apply the new priority's total SLA budget from the original SLA start, accounting for paused time.

## 2. TAT and working hours
Decision: TAT runs continuously, 24 hours a day, including weekends and public holidays.

Example: a High-priority ticket created at 11:00 PM Saturday with a four-hour TAT is due at 3:00 AM Sunday, assuming no pause.

Reasoning: the brief does not define business hours, and a continuous clock is deterministic and simple to explain.

## 3. Waiting for the member
Decision: pause the SLA clock when support explicitly requests information from the member.

- Ticket workflow status remains `IN_PROGRESS` (or its current non-terminal status).
- SLA record is marked paused and `paused_at` is set.
- When the member replies, calculate paused duration, add it to `total_paused_seconds`, clear `paused_at`, and move `due_at` forward by the paused duration.
- A member reply should resume the clock only when the ticket was actually waiting on the member.
- The pause/resume event is written to ticket history.

Reasoning: the support team should not be penalised for time spent waiting for information it cannot obtain independently.

## 4. Escalation
- Scheduler checks active, unpaused SLAs periodically.
- If `now_utc > due_at` and ticket is not resolved/closed, escalate it.
- Set ticket status to `ESCALATED` and preserve its previous workflow status in `previous_status`.
- Write a history event with actor `system` (nullable actor or dedicated system identity) and reason `SLA deadline exceeded`.
- Create an in-app notification for the Support Head.
- Escalation must be idempotent.

When an agent resumes work on an escalated ticket, the system can restore the preserved workflow status while keeping the escalation history and notification.

## 5. Resolution, closure and reopening
- Agent marks ticket `RESOLVED`; record `resolved_at`.
- Member confirms resolution; ticket becomes `CLOSED`; record `closed_at`.
- Member may reopen within the admin-configured number of days from resolution and while below the configured maximum reopen count.
- Reopen requires a reason.
- Reopening clears the current resolved/closed timestamps as appropriate, increments `reopen_count`, records history and starts a new SLA cycle using the ticket's current priority.
- A ticket cannot be reopened after the configured window or maximum count is reached.

## 6. Status and SLA are separate concepts
The required statuses are Open, In Progress, Resolved, Closed, Reopened and Escalated. The system also needs a waiting-for-member condition to pause SLA. To avoid inventing an extra mandatory workflow status, represent this as SLA pause state (`ticket_sla.is_paused`) plus a visible UI indicator. The ticket's primary status remains unchanged while paused.

## 7. Authentication
Login is mocked for the assessment. Provide demo users for all three roles. Backend endpoints must still enforce role permissions based on the selected demo identity/session; frontend-only role hiding is insufficient.

## 8. Scope boundaries
Core scope: member ticket creation/list/detail/replies/confirmation/reopening; agent queue/search/filter/assignment/replies/priority override/resolution; admin configuration and dashboard; SLA pause/resume/escalation; audit history.

Bonus scope after core: internal linked tickets, auto-close, saved replies. Do not compromise core requirements to implement bonus items.

## 9. Analytics definitions
- Open count: tickets in OPEN, IN_PROGRESS or REOPENED.
- Overdue count: unresolved tickets whose active SLA deadline has passed and which are not yet escalated (or show separately as breached, if preferred).
- Escalated count: tickets currently in ESCALATED status.
- Resolved today: tickets with `resolved_at` within the current local calendar day.
- Average resolution time: average active elapsed time from SLA start to resolution, excluding paused intervals. Clearly label the metric and use a consistent definition.
- Tickets by category: count grouped by category for the selected period.
