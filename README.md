# Concave Support Desk

A role-based customer support ticketing system with SLA tracking, automated escalation, and ticket lifecycle management, built for Concave Insights.

## 1. Project Overview

Concave Support Desk is a centralized ticket management platform designed to streamline participant support operations at Concave Insights.

The system enables survey participants to raise support requests, allows support agents to manage and resolve tickets, and provides administrators with visibility into ticket performance, service-level agreements (SLAs), and escalations.

The project follows a modular monolith architecture with a React frontend, Python FastAPI backend, and PostgreSQL database.

**Current status:** Phase 1 scaffold completed. Core ticketing workflows and business functionality are under development.

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
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend API: http://localhost:8000

API documentation: http://localhost:8000/docs

Health check: http://localhost:8000/api/health

### Run backend tests

From the `backend/` directory:

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

Authentication and role-based demo accounts are not yet implemented.

Demo login credentials and sample ticket data will be documented here once the corresponding functionality is available.

## 5. Features

### Planned functionality

- Member ticket creation and ticket tracking.
- Support agent ticket queue and management.
- Role-based access for Members, Support Agents, and Support Heads.
- Category-based ticket priority assignment.
- SLA tracking and automatic escalation.
- Ticket resolution, closure, and reopening workflows.
- Support dashboard with ticket performance metrics.
- Ticket history and audit trail.
- In-app notifications.

### Currently implemented

- React and Vite frontend scaffold.
- FastAPI backend scaffold.
- PostgreSQL Docker Compose configuration.
- Backend health-check endpoint.
- Initial project structure and configuration.

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

The database schema will be implemented through SQLAlchemy models and Alembic migrations.

Refer to:
- `design/02_database_design.md`
- `design/01_user_flows.md`

## 7. API Endpoints

### Currently available

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Backend health check |

Additional endpoints for authentication, ticket management, replies, dashboards, and administration will be documented as they are implemented.

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
- **Escalation:** Overdue unresolved tickets are automatically escalated, with notifications to the Support Head.
- **Ticket lifecycle:** Members can confirm resolution or reopen eligible tickets within configured limits.

Further business rules and architectural decisions are documented in `/design`.

## 9. Known Issues and Next Steps

### Known issues

- Authentication and authorization are not yet implemented.
- Ticket creation and management workflows are not yet implemented.
- SLA calculation and automated escalation are not yet implemented.
- Dashboard metrics and notifications are not yet implemented.
- Demo accounts and sample ticket data are not yet available.

### Next steps

1. Implement database models and migrations.
2. Implement authentication and role-based access.
3. Build member ticket creation and tracking.
4. Build the support agent ticket management interface.
5. Implement SLA tracking and automated escalation.
6. Build the Support Head dashboard.
7. Add automated tests and sample data.
8. Complete documentation and final walkthrough.

---

**Repository:** https://github.com/OSh3081/Concave-Support-Desk