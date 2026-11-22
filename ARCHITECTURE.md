# Ledgerwise AI SDR: architecture exploration

Second, deeper pass, 2026-11-19. Built around your stack: **Python (FastAPI or Django) + LangGraph + Next.js/React**.
Read [BRIEFING.md](BRIEFING.md) first for the case summary.

---

## 0. TL;DR, my recommendation

| Layer | Pick | One-line reason |
|---|---|---|
| Agent | **LangGraph 1.x** with an **AsyncPostgresSaver** checkpointer | `interrupt()` + `Command(resume=…)` maps exactly onto "human approves / takes over" |
| API | **FastAPI** (async) + SQLAlchemy 2 + Alembic + Pydantic v2 | LangGraph is async; same Pydantic models for API, LLM structured output and DB |
| DB | **Postgres on Neon** (free) | One DB for app data **and** LangGraph checkpoints. Doesn't get *paused* after 7 days like Supabase free |
| Long jobs | **No Redis.** FastAPI background task + LangGraph durable checkpoints + `agent_runs` table | Fewer moving parts. If the server restarts, the run resumes from its checkpoint |
| Frontend | **Next.js (App Router) + TanStack Query + shadcn/ui *re-themed*** on Vercel | Your stack. Free hosting that never sleeps |
| Backend host | **Render free + keep-warm ping**, or Fly.io/Koyeb if you're OK adding a card | Render sleeps after 15 min idle, so a ping every 10 min is needed (750 free h/month = 24/7) |
| LLM | Claude: a bigger model for writing/replies, a small one for classifying | Reliable structured output and rule-following |
| Email | **Resend** outbound + inbound webhook | Real threads |
| Calendar | **Cal.com API v2** (`/v2/slots`, `/v2/bookings`) | Real free slots and real bookings |

**Django instead?** Django + Ninja gives you an admin and migrations for free, and works fine. FastAPI wins here because the frontend is Next.js anyway (you don't need Django templates or admin for the client), and because LangGraph/async/Pydantic fit FastAPI natively. If you like having an admin for debugging, **SQLAdmin** adds one to FastAPI in about 20 lines.

---

## 1. Three architecture options

### A. FastAPI + LangGraph + Next.js, split hosting ⭐ recommended
```
[Next.js on Vercel] ──REST/SSE──> [FastAPI on Render/Fly]
                                     ├─ LangGraph graphs (research, reply)
                                     ├─ Postgres (Neon): app tables + checkpoints
                                     ├─ Exa / Firecrawl / SEC / ATS APIs
                                     ├─ Resend (send + inbound webhook)
                                     └─ Cal.com (slots + bookings + webhook)
```
- ✅ Clean split, your stack, easy to explain in the interview.
- ⚠️ Two deployments; the backend free tier sleeps (handled by the keep-warm ping).

### B. Django + Ninja + LangGraph + Next.js
Same shape. Use Django's ORM, admin and auth. Run LangGraph inside Ninja async views.
- ✅ Admin and auth for free; robust.
- ⚠️ Mixing Django's ORM with async LangGraph means `sync_to_async` friction, and you'd keep two model layers (Django models plus Pydantic for the LLM).

### C. Everything on Vercel (Next.js + FastAPI as Vercel Python functions)
Vercel now runs FastAPI with zero config on its Python runtime (default max duration 300s with Fluid compute).
- ✅ One deployment, nothing ever sleeps, $0.
- ⚠️ Long research must be split into small per-company calls (fine, 30–60s each). No long-lived workers. Less "real backend" to talk about.
- Good **fallback** if Render gives you trouble on deploy day.

---

## 2. The LangGraph agents (the heart of the interview)

Two graphs plus one small sourcing graph. All share state typed with Pydantic and are checkpointed in Postgres (`thread_id` = company id or email-thread id).

### 2.1 `sourcing_graph`: find ≥30 candidate companies
```
seed_queries ──> search (Exa / SEC Form D / ATS boards) ──> dedupe+normalize domain
             ──> quick_filter (US? e-com? not Fortune 500?) ──> candidates[]  (≈60–80)
```
Several sources at once, so the list isn't just one search engine's opinion:
1. **Exa semantic search**: "independent Shopify DTC brand that sells on Amazon and is opening wholesale", "e-commerce brand hiring bookkeeper/controller", etc.
2. **SEC EDGAR Form D full-text search** (free; **tested live**: `efts.sec.gov/LATEST/search-index?forms=D&q="Retailing"` returned 58 filings since Sep 2026). This is official proof that a company "recently raised money" **and** it lists executive names (founder/CEO), so it covers both the signal and the contact.
3. **Public ATS job boards**: Greenhouse `boards-api.greenhouse.io/v1/boards/{co}/jobs`, Lever `api.lever.co/v0/postings/{co}`, Ashby `api.ashbyhq.com/posting-api/job-board/{co}` (Ashby **tested live**, no key needed). These prove "hiring for finance/ops" with a link.

### 2.2 `research_graph`: one run per company, fanned out with `Send`
```
             ┌─> scrape_site (Firecrawl: home, about, careers, press)
start ──────┼─> detect_platform (Shopify headers/CDN: tested live)  ──┐
             ├─> jobs_signal (ATS APIs)                                 ├─> extract_evidence ──> qualify ──> draft_email
             ├─> funding_signal (Form D + news via Exa)                 │      (LLM → list[Evidence])   (rubric,   (only cites
             └─> find_contact (About page / Form D related persons) ───┘                               evidence ids) evidence ids)
                                                                                                                  │
                                         ┌──────────── fail (max 2 retries) ─────────── verify_email <─────────┘
                                         │                                       (code + LLM checker)
                                         └─ pass ──> interrupt("approve_email")  ⏸  ← human approves/edits/rejects in UI
                                                         │ Command(resume={action, edited_body})
                                                         └─> send_email (Resend) ──> audit_log
```
**Key ideas you can defend:**
- **`Evidence` is the only source of truth**: `{id, company_id, claim, quote, url, source_type, fetched_at}`. `qualify` and `draft_email` return structured output whose every reason or sentence points to `evidence_ids`. **No evidence id means the claim doesn't exist.** That covers rule 2 in the data structure itself.
- **Scoring rubric** (structured output, each line backed by evidence): ICP fit (US, e-com channel, size estimate), why-now signals (hiring / funding / new channel), contact found. Shown in the UI as a breakdown, not a magic number. Revenue is marked **"estimate"** with a confidence level.
- **`verify_email`**: deterministic checks first (regex for `$`, "price", "per month", numbers that aren't in the evidence; length; unsubscribe footer present), then an LLM-judge that maps each sentence to an evidence id. Failure loops back to the draft step at most twice, then goes to a human.
- **Idempotency gotcha**: code before `interrupt()` runs **again** on resume, so DB writes there must be upserts. Good thing to know in the interview.

### 2.3 `reply_graph`: one run per incoming email
```
inbound webhook ──> load_thread ──> hard_guards (code) ──┬─ STOP/unsubscribe/not interested ──> suppress + close ✋
                                                           └─ otherwise
                    ──> classify (small model, multi-label + confidence)
                         labels: question | objection | price_ask | bot_ask | wants_meeting | picks_slot |
                                 referral | ooo | negative | unclear
                    ──> router
                         ├─ bot_ask        → honest "I'm an AI assistant for Ledgerwise; a human can join anytime"
                         ├─ price_ask      → no number; "pricing depends on volume, let's cover it on a call" + offer slots
                         ├─ wants_meeting  → cal_slots(3, prospect TZ) → propose
                         ├─ picks_slot     → cal_book → confirm → meeting row
                         ├─ question/objection → answer ONLY from the approved Ledgerwise KB (kb_articles)
                         ├─ referral       → note new contact, ask human
                         ├─ ooo            → schedule a follow-up, no reply
                         └─ unclear / low confidence / angry / legal → handoff(reason) ✋
                    ──> verify_reply (same checker + "no price", "no made-up facts", "honest about AI")
                    ──> autonomy gate: high confidence AND autopilot on → send
                                       else → interrupt("approve_reply") ⏸
```
- **Multi-label** matters: "not me, try Ana, and remove me" is a referral **and** an unsubscribe. The unsubscribe wins.
- **Hard guards run before the LLM**, so missing an unsubscribe can't come down to a model's mood.
- **Takeover**: a human clicks "Take over", `threads.mode = human`, and the graph never auto-sends on that thread again. It can still *suggest* a draft in a side panel ("whisper mode").
- **Ledgerwise KB**: a small, approved FAQ (services, process, onboarding, who they serve). Since Ledgerwise is fictional, **you write it** and the agent can't invent beyond it. This is also rule 2, applied to our own company.

---

## 3. Data model (Postgres)

```
users            (id, email, name, password_hash, role)
companies        (id, name, domain, hq_state, platforms[], channels[], employee_est, revenue_est,
                  revenue_confidence, status[candidate|qualified|disqualified|contacted|meeting|closed], score)
contacts         (id, company_id, name, title, email, email_confidence, source_evidence_id)
evidence         (id, company_id, claim, quote, url, source_type[site|job|sec|news|shopify], fetched_at)
qualifications   (id, company_id, score, fit_json, reasons[{text, evidence_ids[]}], model, created_at)
threads          (id, company_id, contact_id, mode[agent|human|stopped], state[...], last_message_at)
messages         (id, thread_id, direction[out|in], status[draft|approved|rejected|sent|received],
                  subject, body, evidence_ids[], classifier_json, confidence, provider_message_id)
approvals        (id, message_id, decision, edited_body, decided_by, decided_at)
handoffs         (id, thread_id, reason, created_at, resolved_by, resolved_at)
suppressions     (email PK, domain, reason, source_message_id, created_at)   -- checked before EVERY send
meetings         (id, thread_id, cal_booking_uid, start_at, end_at, attendee_email, status, prep_brief)
kb_articles      (id, title, body, approved)
agent_runs       (id, graph, thread_id, status, started_at, finished_at, cost_usd, tokens, error)
audit_events     (id, actor[agent|user], action, entity, entity_id, payload_json, created_at)
settings         (autopilot_level, daily_send_cap, sender_name, ...)
eval_cases / eval_results  (for the reply test set: input, expected, actual, pass)
```
Plus the LangGraph checkpoint tables (created by `AsyncPostgresSaver.setup()`).

---

## 4. API endpoints (FastAPI)

```
AUTH        POST /auth/login · POST /auth/logout · GET /me

COMPANIES   GET  /companies?status=&min_score=&signal=&q=      (table)
            GET  /companies/{id}                                 (detail: evidence, score breakdown, contacts, thread)
            PATCH /companies/{id}                                (manual status / disqualify)
            POST /companies/{id}/requalify

RESEARCH    POST /runs/sourcing                    → {run_id}   (start the sourcing graph)
            POST /runs/research {company_ids[]}    → {run_id}
            GET  /runs/{id}  ·  GET /runs/{id}/events (SSE live progress: "reading allbirds.com/about…")

REVIEW      GET  /review-queue                     (drafts waiting: first emails + replies)
            POST /messages/{id}/approve            → resumes graph with Command(resume=approve)
            POST /messages/{id}/edit  {body}       → re-runs verify on the edited text, returns warnings
            POST /messages/{id}/reject {reason}
            POST /messages/{id}/regenerate {instruction}

INBOX       GET  /threads?mode=&needs_human=
            GET  /threads/{id}                     (messages + classifier labels + agent reasoning)
            POST /threads/{id}/takeover   ·  POST /threads/{id}/release
            POST /threads/{id}/send {body}         (human sends manually)
            POST /threads/{id}/simulate-reply {body}   ← demo button: acts as the prospect

MEETINGS    GET  /meetings  ·  GET /meetings/{id}  (with prep brief)
            GET  /calendar/slots?days=5            (proxy to Cal.com)

WEBHOOKS    POST /webhooks/resend/inbound          (email.received → reply_graph)
            POST /webhooks/cal                     (booking created/cancelled)

ADMIN       GET/PUT /settings · GET/POST /kb · GET /suppressions · GET /audit?entity=
            GET  /evals  ·  POST /evals/run        (run the reply test set, show score)
            GET  /health                           (keep-warm ping target)
```

---

## 5. Repo layout (monorepo)

```
ledgerwise-sdr/
├─ backend/
│  ├─ app/main.py, api/ (routers), models/ (SQLAlchemy), schemas/ (Pydantic)
│  ├─ agents/ sourcing_graph.py · research_graph.py · reply_graph.py · state.py · prompts/
│  ├─ tools/  exa.py · firecrawl.py · sec_edgar.py · ats.py · shopify.py · resend.py · calcom.py
│  ├─ guards/ rules.py (price regex, suppression, unsubscribe words) · verifier.py
│  ├─ evals/  reply_cases.yaml · run_evals.py
│  └─ alembic/, tests/, pyproject.toml (uv)
├─ frontend/  (Next.js app router)
├─ CLAUDE.md · BRIEFING.md · ARCHITECTURE.md · HOW_I_WORKED.md
└─ docker-compose.yml (local Postgres)
```

---

## 6. Frontend: screens and ideas that stand out

Screens the brief requires, plus a few that make the Loom memorable:

1. **Today** (home): "Overnight the agent researched 12 companies, drafted 9 emails, answered 4 replies, booked 1 call." Then **"Needs you"** (approvals + handoffs) and **today's calls**. Sales teams start their day here.
2. **Companies**: dense table. Score shown as a small *breakdown bar* (fit / why-now / contact), and **signal chips** ("Hiring: Controller · 3d ago", "Raised $2.1M · Form D", "Now on Amazon"). Clicking a row opens a drawer with the **dossier**.
3. **Dossier** (company detail): research shown as **footnoted evidence**. Every claim gets a superscript; hovering shows the quote and the source link. The score is explained in plain English.
4. **Review queue**: an email with **inline citation markers**. Keyboard: `J/K` move, `A` approve, `E` edit, `R` reject. While you edit, the verifier runs live and underlines sentences without a source ("this claim has no evidence").
5. **Inbox**: threads labeled with who's in charge: 🤖 *Agent handling* · ✋ *Needs you* · 👤 *You're driving* · ⛔ *Stopped*. A clear **Take over** button. Agent reasoning can be expanded ("classified: price_ask 0.94 → offered slots, no price").
6. **Calls**: week calendar plus a **prep brief** for each call (built from the evidence, so the salesperson walks in prepared).
7. **Guardrails page**: the 5 rules as live cards with counters ("Blocked 3 price mentions · 2 unsubscribes honored · 5 handoffs this week"). This builds the client's trust and **shows the reviewers your safety design**.
8. **Autonomy dial**: *Draft only → Auto-reply when confident → Autopilot*. Trust grows step by step.
9. **Evals page**: the reply test-set scoreboard. The reviewers see your numbers in the product itself.

---

## 7. Design directions (no AI-slop look)

AI-generated UIs all look alike: purple gradients, Inter everywhere, big rounded cards, a colored left border on cards, lots of empty space. The fix is **deliberate design tokens** (fonts, colors, radius, density) chosen *for this client*, and a CLAUDE.md that makes the AI follow them.

| Direction | Feel | Fonts | Palette | Why it fits |
|---|---|---|---|---|
| **1. Ledger** ⭐ | Accounting paper, calm, exact | Serif headings (Newsreader/Fraunces) + mono tabular numbers (IBM Plex Mono) + plain sans for UI | Warm paper `#F6F3EC`, ink navy, ledger green, red only for "stop" | **Ledgerwise is a bookkeeping firm.** Ruled lines, footnote citations, numbers in columns. The design tells their story |
| **2. Dossier / Broadsheet** | Editorial, research-heavy | Newspaper serif headlines + grotesk body | Black on white, one vermilion accent, hairline rules | Each company reads like a briefing file; puts the research front and center |
| **3. Control room** | Fast, dense, keyboard-first | Grotesk + mono | Graphite / off-white, signal colors only for status | Linear/Attio-style pro tool for power users. Safe, but closer to "every SaaS" |

**My pick: Ledger.** It differentiates you, ties the UI to the client's brand ("we built this *for* Ledgerwise"), and footnote citations make rule 2 visible. A mockup of all three directions is in the design artifact.

---

## 8. Making the demo testable (important)

- **Never cold-email real companies.** Real research, but outgoing mail goes **only to your test inboxes** (each company has a "demo routing" address; the real contact is shown and labeled).
- **Two ways to reply:** (a) really reply from your Gmail, which goes through the Resend inbound webhook into `reply_graph`; (b) a **"Simulate prospect reply"** box in the thread, so the reviewers can try "Are you a bot?" or "How much does it cost?" themselves in 5 seconds.
- **Seed data:** 30+ researched companies and some finished threads (one booked call, one unsubscribe, one handoff) so the app looks alive on first login.

---

## 9. Evals (the "numbers" for HOW_I_WORKED)

- `reply_cases.yaml`: **~60 cases** × expected `{labels, action, must_not}`. Includes nasty ones: hidden unsubscribe ("pls don't email again, thx"), price bait ("ballpark is fine"), bot trap ("are you a real person?"), referral + opt-out, a time zone mix-up, "next Tuesday 3pm" when that slot is taken.
- Hard metrics that must be **100%**: unsubscribes honored, no price quoted, honest about being AI. Soft metrics: correct action %, correct handoff %.
- Grounding: for all 30+ emails, % of sentences mapped to evidence, plus a manual spot-check of 10 source links.
- Run in CI or with `POST /evals/run`; show the results on the Evals page.

---

## 10. Cost (rough)

Everything is free tier except LLM tokens. Research for ~40 companies plus drafts plus ~100 test replies is likely a **few dollars** with Claude (log real token cost per run in `agent_runs.cost_usd`, which HOW_I_WORKED asks for). Gemini's free tier is the $0 fallback.

---

## 11. Decisions for you

1. FastAPI ⭐ or Django?
2. Hosting: Render + ping ⭐ / Fly or Koyeb (card) / everything on Vercel (option C)?
3. LLM: Claude ⭐ or Gemini free?
4. Design: Ledger ⭐ / Dossier / Control room?
5. When did the 72h timer start?

---

### Sources
- LangGraph HITL: [LangChain docs](https://docs.langchain.com/oss/python/langchain/human-in-the-loop), [interrupt tutorial](https://www.agentnotebook.dev/tutorials/langgraph-human-in-the-loop), [FastAPI + HITL](https://shaveen12.medium.com/langgraph-human-in-the-loop-hitl-deployment-with-fastapi-be4a9efcd8c0), [production guide](https://prodinit.com/blog/langgraph-production-guide), [LangGraph 1.0](https://blog.langchain.com/langchain-langgraph-1dot0), [platform pricing](https://www.langchain.com/langgraph-platform-pricing), [subgraphs vs supervisor](https://callsphere.ai/blog/td30-fw-langgraph-subgraphs-vs-supervisor-pattern-2026)
- Frameworks/hosting: [FastAPI vs Django](https://encore.dev/articles/fastapi-vs-django), [Django Ninja](https://dev.to/j4kh/django-ninja-the-sweet-spot-between-djangos-simplicity-and-fastapis-power-45cg), [free hosting 2026](https://snapdeploy.dev/state-of-free-hosting), [Python hosting limits](https://www.runxbuild.com/blog/free-python-hosting/), [Supabase pausing](https://supabase.com/kb/faqs/platform/free-project-pausing), [Neon vs Supabase free](https://neon.com/guides/neon-vs-supabase-free-plan), [FastAPI on Vercel](https://vercel.com/docs/functions/runtimes/python), [task queues for LLM apps](https://dangquan1402.github.io/llm-engineering-notes/2026/04/02/lightweight-task-queues-for-llm-apps.html)
- Data: [ATS public APIs](https://fantastic.jobs/article/ats-with-api), [Shopify detection](https://www.elsner.com/shopify-ecommerce-platform-detection-methods/), [search API comparison](https://parallel.ai/articles/best-free-web-search-api.md), [SEC Form D data](https://sec-api.io/docs/full-text-search-api)
- Design: [AI slop patterns](https://noqta.tn/en/blog/ai-design-slop-overused-ui-patterns-fix-2026), [anti-slop guide](https://www.925studios.co/blog/ai-slop-web-design-guide), [Attio UI gallery](https://saasui.design/application/attio), [serifs in UI](https://fontalternatives.com/blog/text-serifs-comeback-2026/), [AI UX patterns](https://www.aiuxplayground.com/patterns), [agent UX checklist](https://www.agenticwire.news/article/agent-ux-design-patterns)
