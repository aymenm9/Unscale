import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db as app_db
from app.api import campaigns, mail
from app.api.routes import public, router
from app.config import settings
from app.services.followups import run_due

log = logging.getLogger(__name__)
FOLLOWUP_EVERY_SECONDS = 15 * 60


def _followup_loop(stop: threading.Event) -> None:
    """The follow-up timer: every 15 minutes, send follow-ups that are due."""
    while not stop.wait(FOLLOWUP_EVERY_SECONDS):
        db = app_db.SessionLocal()
        try:
            run_due(db)
        except Exception:
            log.exception("follow-up timer failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop = threading.Event()
    if settings.run_followup_timer:
        threading.Thread(target=_followup_loop, args=(stop,), daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="Ledgerwise SDR API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Used by the keep-warm ping and deploy checks."""
    return {"status": "ok"}


app.include_router(public)
app.include_router(mail.public)
app.include_router(router)
app.include_router(campaigns.router)
app.include_router(mail.router)
