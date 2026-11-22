# Ledgerwise AI SDR

An AI sales rep for **Ledgerwise**, a made-up US bookkeeping firm for e-commerce brands. The agent finds companies, qualifies them, writes the first email, answers replies and books calls. A web app lets a non-technical sales team check and control every step.

Built for the Unscale AI Engineer case study.

## Try it

- **App:** https://ledgerwise-ai-sdr.vercel.app
- **Login:** `sales@ledgerwise.test` / `ledgerwise-demo`
- The backend runs on Render's free plan and sleeps after 15 minutes without visits. The first visit shows a wake-up screen for about a minute.
- **No real prospects get emailed.** Every outgoing email goes to a demo inbox. To see the whole loop, put your own address in **Test mode** on the home page, then reply to the emails you receive.

## What the agent does

| Step | What happens | Where a person steps in |
|---|---|---|
| Search | An agent with search tools picks its own keywords and finds US e-commerce brands | Starts a campaign with a target and categories |
| Quick filter | A decision model (Gemini Decision 1, Clef as backup) drops clear misses, each with a reason | Sees every dropped company and the reason under **Not chosen** |
| Research | Reads the company's own site; every fact is stored with its URL and an exact quote | Opens the report and its sources |
| Qualify | Score plus reasons, each reason tied to a stored quote | Sees score, reasons, sources |
| Write | A short first email; code and an LLM fact checker verify every sentence against the evidence | **Approves, edits or rejects every first email** |
| Reply | Classifies the reply, then answers, offers real free slots, hands off or stops | Gets a "needs a person" flag with the reason; can take over any thread |
| Book | Books the picked slot into the calendar | Sees it under **Calls** |

**Rules the agent can't break** (checked by code first, LLM second):
1. Never quotes a price.
2. Never states a fact without a stored source.
3. "Stop", "unsubscribe" or "not interested" puts the person on the do-not-contact list forever.
4. Answers honestly when asked if it is a bot.
5. Hands off to a person when unsure.

When the free AI providers hit their limits, the app says so: a banner shows when the AI comes back, and campaigns stop with the reason.

## Stack

- **Backend:** Python 3.12, FastAPI, LangGraph, SQLAlchemy and Alembic, Postgres. Every LLM answer is validated with a Pydantic schema.
- **Frontend:** Next.js 16, TanStack Query, Tailwind.
- **AI:** free providers only, with a rotating pool and fallbacks: Groq, OpenCode Zen, Gemini, Cloudflare Workers AI, and the Gemini Decision 1 and Clef decision models.
- **Tools:** Tavily (search), Jina Reader (read sites), Shopify `/meta.json` (store data), Hunter (emails), Resend (send and receive email).
- **Hosting:** Vercel (frontend), Render (backend and Postgres). Total cost: $0.

## Repo map

| Path | What is there |
|---|---|
| `backend/app/agents/` | The agents: `search`, `quick_filter`, `researcher`, `qualifier`, `writer`, `reply`, `pipeline` (the campaign graph), `llm` (the only place that calls an LLM) |
| `backend/app/guards/` | Deterministic rule checks: price, sources, opt-out, bot question |
| `backend/app/api/` | REST API used by the frontend |
| `backend/tests/`, `backend/evals/` | 181 tests and the qualifier eval |
| `frontend/src/app/` | The pages: home, campaigns, companies, approve drafts, conversations, calls, test inbox, do not contact, activity log |
| `docs/AGENTS.md` | Each agent in detail: inputs, prompts, models, checks |
| `HOW_I_WORKED.md` | How it was built with Claude Code: process, tools, rules, AI mistakes, numbers, next steps |
| `CLAUDE.md` | The rules given to the AI coding tool |

## Run it locally

```bash
# Backend (needs Python 3.12; .env.example uses SQLite, set DATABASE_URL for Postgres)
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # add your free API keys
.venv/bin/alembic upgrade head && .venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --port 8000

# Frontend (needs Node 22)
cd frontend
npm install && npm run dev    # http://localhost:3000
```

Tests: `cd backend && .venv/bin/pytest -q`
