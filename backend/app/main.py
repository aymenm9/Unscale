import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db as app_db
from app.agents import llm
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
@app.get("/api/health")  # the frontend only forwards /api/*, so its wake-up screen polls this one
async def health() -> dict[str, str]:
    """Used by the keep-warm ping and deploy checks."""
    return {"status": "ok"}


@app.exception_handler(llm.LLMFailed)
@app.exception_handler(llm.LLMNotConfigured)
async def ai_unavailable(_request: Request, error: Exception) -> JSONResponse:
    """No AI provider could answer. Say so in plain words instead of a bare 500/503:
    'all free limits used up, back in about 14 minutes' or 'the providers are down'."""
    rate_limited = isinstance(error, llm.LLMFailed) and error.rate_limited
    retry_in = error.retry_in if isinstance(error, llm.LLMFailed) else None
    return JSONResponse(
        status_code=503,
        content={
            "detail": llm.user_message(error),
            "code": "ai_limits_used_up" if rate_limited else "ai_unavailable",
            "retry_in_seconds": retry_in,
        },
        headers={"Retry-After": str(retry_in)} if retry_in else None,
    )


app.include_router(public)
app.include_router(mail.public)
app.include_router(router)
app.include_router(campaigns.router)
app.include_router(mail.router)
