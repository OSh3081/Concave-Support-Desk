from contextlib import asynccontextmanager
from datetime import timezone
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.support import router as support_router
from app.api.routes.tickets import router as ticket_router, support_router as support_ticket_router
from app.services.escalation import escalate_overdue_tickets


_scheduler_lock = Lock()
_sla_scheduler = None
_sla_scheduler_lifespan_users = 0


def _acquire_sla_scheduler():
    """Start one scheduler per process and share it across overlapping lifespans."""
    global _sla_scheduler, _sla_scheduler_lifespan_users
    with _scheduler_lock:
        if _sla_scheduler is None:
            scheduler = BackgroundScheduler(timezone=timezone.utc)
            scheduler.add_job(
                escalate_overdue_tickets,
                trigger="interval",
                seconds=60,
                id="automatic-sla-escalation",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            scheduler.start()
            _sla_scheduler = scheduler
        _sla_scheduler_lifespan_users += 1
        return _sla_scheduler


def _release_sla_scheduler(scheduler) -> None:
    global _sla_scheduler, _sla_scheduler_lifespan_users
    with _scheduler_lock:
        if scheduler is not _sla_scheduler:
            return
        _sla_scheduler_lifespan_users -= 1
        if _sla_scheduler_lifespan_users == 0:
            scheduler.shutdown(wait=True)
            _sla_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.app_env != "test":
        scheduler = _acquire_sla_scheduler()
        app.state.sla_scheduler = scheduler
    try:
        yield
    finally:
        if scheduler is not None:
            _release_sla_scheduler(scheduler)
            app.state.sla_scheduler = None


app = FastAPI(title="Concave Support Desk API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(ticket_router, prefix="/api")
app.include_router(support_ticket_router, prefix="/api")
app.include_router(support_router, prefix="/api")
