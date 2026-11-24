# Concave Support Desk

A role-based customer support ticketing system with SLA tracking, automated escalation, and ticket lifecycle management, built for Concave Insights.

## 1. Project Overview

Concave Support Desk is a centralized ticket management platform designed to streamline participant support operations at Concave Insights.

The system enables survey participants to raise support requests, allows support agents to manage and resolve tickets, and provides administrators with visibility into ticket performance, service-level agreements (SLAs), and escalations.

The project follows a modular monolith architecture with a React frontend, Python FastAPI backend, and PostgreSQL database.

**Current status:** Backend database foundation, development mock authentication, core ticket APIs, and scheduled SLA escalation are implemented. The frontend experience is under development.

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, TypeScript |
| Routing | React Router |
| Styling | Tailwind CSS 4 |
| API Client | Axios |
| Backend | Python, FastAPI |
| ORM | SQLAlchemy 2 |
| Validation | Pydantic |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Testing | Pytest, FastAPI TestClient |
| Development | Docker Compose |

## 3. Setup and Run

### Prerequisites

- Git
- Python 3.11 or newer
- Node.js 20 or newer and npm
- Docker Desktop or Docker Engine with the Compose plugin

### Clone the repository

```bash
git clone https://github.com/OSh3081/Concave-Support-Desk.git
cd Concave-Support-Desk
```

### Configure and start PostgreSQL

From the repository root:

```bash
cp .env.example .env
docker compose up -d db
docker compose ps
```

### Run the backend

```bash
cd backend
cp .env.example .env
# APP_ENV=development is required for local demo accounts; set production elsewhere.
# Generate a local value, then set JWT_SECRET in backend/.env before continuing.
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
# Keep the sample demo passwords local-only and change them before any non-local use.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload
```

Backend API: http://localhost:8000

API documentation: http://localhost:8000/docs

Health check: http://localhost:8000/api/health

### Run backend tests

> **Required:** Backend tests must use the isolated PostgreSQL test database. Do not run them against the development database. Follow [TEST_DATABASE.md](TEST_DATABASE.md) to start the dedicated service and export its environment before running pytest.

After completing the setup in that guide, run from the `backend/` directory:

```bash
source .venv/bin/activate
pytest
```

### Run the frontend

In a separate terminal, from the repository root:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open the Vite development URL displayed in the terminal, normally http://localhost:5173.

The frontend API base URL is configured using `VITE_API_BASE_URL` in `frontend/.env`.

## 4. Demo Logins and Test Data

The backend provides development-only demo accounts. Set their passwords in `backend/.env` before running the seed process:

| Role | Email | Sample local password |
|---|---|---|
| Member | `member@concave.test` | `MemberDemoOnly!2026` |
| Support Agent | `agent@concave.test` | `AgentDemoOnly!2026` |
| Support Head | `head@concave.test` | `HeadDemoOnly!2026` |

These public sample credentials are for local demonstrations only and must never be used in production. `APP_ENV` is required and must be `development`, `test`, `staging`, or `production`; a missing or invalid value stops application configuration rather than defaulting to development. Demo seeding and login are enabled only when `APP_ENV=development`. The demo password settings must be 12–128 characters. Passwords are hashed with Argon2id before storage. The SYSTEM account has no password and cannot use normal login.

Access tokens expire after 30 minutes by default. `ACCESS_TOKEN_EXPIRE_MINUTES` accepts values from 1 to 1440. For production provisioning, set `APP_ENV=production`; the normal seed command refuses to create public demo accounts. `seed_database(include_demo_accounts=False)` remains available for SYSTEM and default settings without demo users; provision real users through the appropriate production process.

## 5. Features

### Currently implemented

- React and Vite frontend scaffold.
- FastAPI backend scaffold.
- PostgreSQL Docker Compose configuration.
- Backend health-check endpoint.
- Mock authentication with signed bearer tokens and role dependencies.
- SQLAlchemy database models, Alembic migration and demo seed process.
- Member ticket creation and listing, ticket detail and conversation, public replies, resolution confirmation, and eligible reopening.
- Support queue filters and search, ticket assignment and reassignment, and support status transitions.
- Public support replies and internal notes with role-based visibility, plus the Request Information workflow and SLA pause/resume.
- Support priority overrides with required reasons and priority-change audit history.
- Support dashboard metrics and active-agent assignment controls.
- Historical per-cycle SLA records and configuration-change audit history.
- Category priority, TAT, and reopening settings managed by Support Heads.
- UTC SLA deadlines, pause/resume on information requests, and pause accounting through resolution and reopening.
- Automatic SLA escalation every 60 seconds with SYSTEM audit history and Support Head notifications.
- Append-only ticket history, internal reply visibility controls, and in-app ticket notifications.
- Initial project structure and configuration.

### Planned functionality

- Notification inbox and read-state endpoints.

## 6. Database Design

The database design is documented in the `/design` directory.

The proposed schema includes:

- Users
- Tickets
- Ticket Replies
- Ticket History
- Category Priority Settings
- TAT Settings
- Ticket SLA
- Reopen Settings
- Notifications

The implemented database schema is managed through SQLAlchemy models and Alembic migrations.

The `/design` directory is the original Day 2 design submission and is preserved as the design baseline. This document supplements it with implementation details; it does not replace the submission. See [Implementation Decisions](docs/implementation-decisions.md) for the detailed engineering rationale.

Refer to:
- `design/02_database_design.md`
- `design/01_user_flows.md`

## 7. API Endpoints

### Currently available

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Backend health check |
| POST | `/api/auth/login` | Development demo login |
| GET | `/api/auth/me` | Return the authenticated user's profile |
| POST | `/api/tickets` | Create a ticket as a Member |
| GET | `/api/tickets` | List the authenticated Member's tickets |
| GET | `/api/tickets/{ticket_id}` | View an authorized ticket and conversation |
| POST | `/api/tickets/{ticket_id}/replies` | Add a reply or request information |
| POST | `/api/tickets/{ticket_id}/confirm-resolution` | Member confirms resolution and closes the ticket |
| POST | `/api/tickets/{ticket_id}/reopen` | Reopen an eligible closed ticket with a reason |
| GET | `/api/support/tickets` | Paginated support queue with filters and search |
| GET | `/api/support/tickets/{ticket_id}` | View a support ticket and full conversation |
| POST | `/api/support/tickets/{ticket_id}/assign` | Assign or unassign a Support Agent |
| PATCH | `/api/support/tickets/{ticket_id}/status` | Apply a valid support status transition |
| PATCH | `/api/support/tickets/{ticket_id}/priority` | Override priority with a reason |
| GET | `/api/support/dashboard` | View ticket and SLA metrics |
| GET | `/api/support/settings` | Read ticket configuration (Support Head) |
| PATCH | `/api/support/settings/categories/{category}` | Change a category's default priority (Support Head) |
| PATCH | `/api/support/settings/tat/{priority}` | Change priority TAT hours (Support Head) |
| PATCH | `/api/support/settings/reopen` | Change reopen policy (Support Head) |

Automatic SLA escalation runs every 60 seconds while the backend application is running. It considers unresolved OPEN, IN_PROGRESS, and REOPENED tickets whose unpaused SLA deadline has passed; already escalated, resolved, and closed tickets are excluded. It records the dedicated SYSTEM actor and notifies active Support Heads. See `docs/implementation-decisions.md` for concurrency and deployment assumptions.

Interactive API documentation is available at `/docs` when the backend is running.

## 8. Assumptions and Decisions

The following decisions guide the system design:

- **Architecture:** Modular monolith rather than microservices.
- **Backend:** Python FastAPI.
- **Database:** PostgreSQL.
- **Timestamps:** Stored in UTC and displayed in Asia/Kolkata.
- **SLA calculation:** 24/7, including weekends and holidays.
- **Waiting for member:** SLA pauses when support explicitly requests additional information and resumes when the member responds.
- **Priority assignment:** Default priority is determined by ticket category, with authorized support agents able to override it with a recorded reason.
- **Escalation:** Support can manually escalate eligible tickets, and a 60-second background job automatically escalates unresolved tickets after an unpaused SLA deadline passes. The dashboard counts overdue unresolved tickets (including escalated tickets) separately from escalations.
- **Ticket lifecycle:** Members can confirm resolution or reopen eligible tickets within configured limits.

Implementation refinements include per-cycle SLA history alongside mutable current SLA state; pausing active SLA time while awaiting member information; reopening only after closure within the configured window and attempt limit; and preserving elapsed active time and accumulated pauses during priority changes. A deferred database constraint ensures every committed ticket has exactly one SLA row, while configuration audit rows are protected against ordinary mutation. Automatic escalation commits the ticket change, SYSTEM history event and notifications together. Dashboard counts use explicit status and time boundaries; overdue counts include escalated unresolved tickets, while the escalated total is shown separately.

The scheduler is process-local, so this assessment assumes one API worker. Production deployment should use a separate least-privilege runtime database role rather than the local bootstrap role. See [Implementation Decisions](docs/implementation-decisions.md) for the detailed rationale, edge cases and trade-offs.

Further business rules and architectural decisions are documented in `/design`.

## 9. Known Issues and Next Steps

### Known issues

- Authentication is development-only; production identity management, refresh tokens and token revocation are not implemented.
- The scheduler currently starts in every API worker; use one backend worker process. Database row locks prevent duplicate ticket effects across workers, but do not prevent duplicate polling. A dedicated scheduler process needs a scheduler-role switch first.
- The local Compose setup uses the bootstrap database user for backend connections. Before production, configure a separate least-privilege runtime database role; the audit triggers do not prevent a privileged owner from changing or disabling them.
- Notification inbox/read endpoints are not implemented.
- Demo users are seeded, but sample tickets are not seeded.

### Next steps

1. Add notification inbox/read endpoints and sample ticket data.
2. Complete documentation and final walkthrough.

---

**Repository:** https://github.com/OSh3081/Concave-Support-Desk
