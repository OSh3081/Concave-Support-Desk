# System Architecture

## Architecture style
A modular monolith: one React frontend, one FastAPI backend, one PostgreSQL database, and a background scheduler running with the backend for the assessment deployment.

This is intentionally simpler than microservices and is appropriate for a five-day take-home assessment.

## Component responsibilities

### Frontend — React + Vite
- Role-aware routes for Member, Support Agent and Support Head.
- Responsive layouts, with the member portal designed mobile-first.
- Form validation and user-friendly loading, empty and error states.
- API calls isolated in `src/services/`.
- UI role checks improve navigation, but backend authorization remains authoritative.

### Backend — FastAPI
- `api/routes`: HTTP request/response handling.
- `schemas`: Pydantic request and response validation.
- `models`: SQLAlchemy ORM entities.
- `services`: ticket, priority, SLA, escalation and analytics business logic.
- `core`: configuration and authentication helpers.
- `scheduler`: periodic SLA deadline checks.
- `db`: database session management and seed data.

### Database — PostgreSQL
- Stores users, tickets, replies, configuration, SLA state, audit history and notifications.
- Foreign keys enforce relationships.
- Alembic manages schema migrations.

### Background scheduler
- Runs a periodic job, e.g. every 60 seconds.
- Finds unresolved tickets whose SLA is active, not paused and past `due_at`.
- Performs escalation in a database transaction.
- Uses an idempotency guard so an already-escalated ticket does not generate duplicate events/notifications.
- For a production deployment with multiple backend instances, move scheduling to a dedicated worker or use a distributed job/locking mechanism.

## Request flow
1. React submits an HTTP request to FastAPI.
2. FastAPI validates the request with Pydantic.
3. The route checks authentication/role permissions.
4. The route calls a service function.
5. The service reads or writes through SQLAlchemy.
6. PostgreSQL commits the transaction.
7. FastAPI returns a JSON response.
8. React updates the screen.

## Suggested repository structure

```text
concave-support-desk/
├── design/
│   ├── README.md
│   ├── 01_user_flows.md
│   ├── 02_database_design.md
│   ├── 03_system_architecture.md
│   └── 04_business_rules.md
├── frontend/
│   └── src/
│       ├── components/
│       ├── layouts/
│       ├── pages/
│       │   ├── member/
│       │   ├── agent/
│       │   └── admin/
│       ├── services/
│       ├── hooks/
│       ├── context/
│       └── utils/
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── scheduler/
│   ├── alembic/
│   └── tests/
├── README.md
└── .gitignore
```

## Security and reliability baseline
- Validate all request bodies and path/query parameters.
- Enforce member ownership: members can only view and act on their own tickets.
- Enforce agent/admin permissions in backend dependencies.
- Keep secrets in environment variables; commit only `.env.example`.
- Use transactions for state changes, audit events and notifications.
- Use timezone-aware timestamps.
- Add database constraints and indexes for common queue operations.
- Never expose internal replies/notes to members.
