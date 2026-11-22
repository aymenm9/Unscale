# How I worked

Live app: https://ledgerwise-ai-sdr.vercel.app (login `sales@ledgerwise.test` / `ledgerwise-demo`)
Code: https://github.com/aymenm9/Unscale

## First, a disclaimer

I want to be honest about how I approached this, with all respect to Unscale.

1. **I did not put 100% of my time into it.** Friends of mine got the same email and the same take-home without any first-round call, so I was a bit unsure how seriously to take it. I did it anyway because it looked like a fun project.
2. **I used it as a playground for Claude Code.** I use OpenCode on my own projects. I had used Claude Code only at work, where you can't give it freedom with people's data and accounts. On my own accounts I wanted to see how far I could push it: full permissions, connectors, browser access, deployment access, remote control from my phone. Some things I did here (pasting API keys into the chat, letting the agent set them on the hosting platform) I would never do in a real project. All keys get rotated after the review.
3. **I tried things I had never used.** The main one is a fast "decision model" (Gemini Flash Lite) that filters companies before the expensive research step. I had never built one, so I added it to learn.
4. **I used free models only.** I did not know if this project would go anywhere, so I did not want to spend real money on tokens. I used whatever free tier I could get: Groq, Cloudflare Workers AI, OpenCode Zen, Gemini. I did not benchmark these models carefully before using them; I picked them to move fast.
5. **I know Render's free plan is slow and cold-starts.** The backend sleeps after 15 minutes and takes about a minute to wake. I kept it because it is free, and I added a wake-up screen so the app explains the wait instead of looking broken.
6. **I kept my stack.** For a 100% free host, all-JavaScript on Vercel would have been easier. I stayed with FastAPI + Next.js because that is what I like and know.

## How the work went, step by step

### 1. Setup and planning (no code)

I started at work. When I finished, I set up Claude Code on my machine with my skills, the connectors (Google Docs for the brief, Google Drive) and a project `CLAUDE.md`. Then I gave it one big instruction: read the brief, don't write code, understand the project, explore architectures, prepare the repo. I let it run for 2 to 3 hours and came back to review.

What came out of that first run:
- [`BRIEFING.md`](BRIEFING.md): the brief turned into a checklist, plus what already exists online.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): three architecture options with a recommendation (FastAPI + LangGraph + Next.js).
- [`CLAUDE.md`](CLAUDE.md): the rules for the AI (see below).

It did not do everything right the first time. It was asked to open the GitHub repo and didn't (that only happened at the very end). The first research round was also too shallow, so I ran a second one.

### 2. Checking that we understood the same thing

I read the brief myself, then asked Claude to explain the project back to me, and we compared. Where our understanding differed, we discussed it until we agreed. I added requirements of my own at this stage:
- the decision model as a fast first filter;
- a report on every conversation that updates after each round;
- a test inbox so anyone can play the prospect and reply;
- an email sender service that is the only way out, with its own opt-out check;
- HTML emails that look good.

### 3. Research

Two research rounds, run as parallel subagents:
- [`research/SOURCING.md`](research/SOURCING.md): how to find real US e-commerce brands for free, how to estimate revenue and headcount honestly, which signals mean "needs bookkeeping".
- [`research/EMAIL_STYLE.md`](research/EMAIL_STYLE.md): what cold emails work in 2025-2026, voices, HTML vs plain text, reply handling. Its style guide went straight into the writer's system prompt.

I used these findings to write the system prompts and guardrails for the agents.

### 4. Agreeing on the agents, one by one

Before any code, we went through every agent: what it does, what tools it gets, what it outputs, what code checks surround it. We discussed each one until we agreed, then moved to the next. The result is [`docs/AGENTS.md`](docs/AGENTS.md).

One example where I pushed back: Claude first proposed a mostly code-based scraper to find companies. I wanted an agent with search tools that chooses its own keywords, a fast decision model that rejects the obvious misfits, and a separate qualifier that gives reasons. We went with mine.

Another: how much the human approves. We settled on the human approving the **direction** (the first email plus the follow-up strategy), not every single email. After that the agent runs on its own unless it asks for a human, and a human can take over a thread at any time and hand it back.

The final pipeline:

| Step | What it is | Model |
|---|---|---|
| Search agent | LLM with search tools, picks its own queries | Groq / Cloudflare pool |
| Code checks | US, real Shopify store, not seen before (no LLM) | none |
| Decision model | fast yes/no filter on size and fit | Gemini Flash Lite, then Cloudflare |
| Researcher | reads the site and sources, stores facts as evidence (url + quote) | pool |
| Qualifier | score + reasons, each reason cites evidence | pool |
| Contact finder | named person and email from the company's own pages | code + small LLM step |
| Email writer | first email + follow-up strategy, HTML | pool |
| Reply agent (LangGraph) | classifies replies, answers, hands off, books calls, updates the report | pool |
| Compose assistant | rewrites a draft from a human comment | pool |

### 5. Pages and API

Same process for the frontend: we agreed on each page (campaigns, companies with reports, drafts to approve, conversations with "needs a human" flags and progress, calls, test inbox, do-not-contact list, activity log), then on the API endpoints. Then I let Claude build it.

Honestly, this was a fairly simple project. I could have handed over one detailed prompt and let Claude do everything. But I was exploring Claude Code as much as building the product, so I went step by step.

### 6. Design

I let Claude handle most of the design with the frontend-design skill, and told it to explore as many directions as possible. I reviewed them, said what I liked and what was missing, and gave it more rounds. The final one is "direction D": black, white and safety yellow (`#FFC600`), the Archivo font, and a black sidebar. Yellow only means "needs you" or "current".

### 7. Testing it myself and fixing what I didn't like

I ran the app and used it as the sales team would. Things I sent back:
- Approving a draft failed with a 500 error.
- An email-length error ("40 words; this kind of email needs 50-90") was shown to the user. That should be a guardrail the agent fixes by retrying, not the user's problem. Fixed.
- "Rewrite with AI" changed too much of the email. Now it keeps the original wording, and a code check retries if less than 45% of the words survive (unless the comment asks for a full rewrite).
- The app felt complicated: you couldn't launch a campaign from the campaigns page, and campaigns had no names. Fixed both, and added a campaign filter on companies.
- The HTML email template needed more color and branding.
- I added test mode: put your own email on the home page, every outgoing email goes there, and you can reply and watch what happens. Plus a short "how to use the app" panel.
- Back buttons that weren't styled.

### 8. Tuning the decision model

I asked Claude to take random companies from real campaigns and check whether the scores made sense. They didn't: a candle studio scored 100, and a school's merchandise shop got "maybe". The qualifier prompt was rewritten with a points guide, and code rules now cap the score when size proof says too big or too small. More on this under the accuracy numbers.

### 9. Deployment (done from my phone)

I did the end of the project with Claude Code's remote control from my phone, which was fun. Claude created the GitHub repo, pushed it, and deployed everything itself through the Render and Vercel connectors: backend + Postgres on Render, frontend on Vercel. It also added the wake-up screen for Render's cold start.

## Tools per step, and why

| Step | Tool | Why |
|---|---|---|
| Coding agent | Claude Code (desktop app + phone remote control) | what I wanted to explore |
| Planning, research | Claude Code subagents, web search | parallel deep research while I was at work |
| Backend | FastAPI, SQLAlchemy, Alembic | my usual stack, simple and explicit |
| Agents | LangGraph + OpenAI-compatible clients | I like LangGraph; every free provider speaks the OpenAI API |
| LLMs | Groq, Cloudflare Workers AI, OpenCode Zen, Gemini Flash Lite, in rotating pools | free; if one hits its limit the next one answers, if all fail it hands off to a human |
| Structured output | pydantic schemas on every LLM call | every output is validated before use |
| Web search / pages | Tavily search, Jina Reader, Shopify's public store data | free tiers; Shopify's store data proves the platform and product count |
| Contacts | company's own pages first, Hunter as backup | no LinkedIn scraping; direct page fetches check robots.txt |
| Email | Resend (free) | sending + inbound webhooks for replies |
| Booking | our own slot service (business hours minus calls already booked) | simple and free; Cal.com is the planned swap, see next steps |
| Frontend | Next.js 16, Tailwind, TanStack Query | my usual stack |
| Hosting | Render (backend + Postgres), Vercel (frontend) | free plans |

## Rules I gave the AI

All in [`CLAUDE.md`](CLAUDE.md). The business rules: never quote a price; never state a fact without a stored evidence item (url + quote); stop/unsubscribe/"not interested" goes on the suppression list forever; answer honestly if asked "are you a bot"; hand off to a human when unsure.

The engineering rules: code I can understand line by line, no clever abstractions; every LLM call returns validated structured output; **guardrails are deterministic code first, LLM second**; every agent action goes to an audit log; outbound email only to demo/test addresses; add a test whenever reply or guardrail logic changes; ask before adding a paid service.

Examples of "code first" guardrails: a price regex blocks any reply containing a price before it can be sent; opt-out words are caught before the LLM even sees the email; a reply that forgets to admit it's an AI when asked gets the disclosure added by code; every fact in an email must point to an evidence id that exists.

## Where the AI got things wrong

- Didn't open the GitHub repo when first asked; it only happened at deployment time.
- First research round was too shallow; needed a second round.
- The qualifier gave scores that were far too generous (100 for brands with no real need signal), counted the same fact twice, and called "no staff mentioned" proof of a one-person company. The first fix overcorrected and made a good prospect "poor".
- "Rewrite with AI" rewrote whole emails instead of making the one change asked for.
- Showed a guardrail failure (email too short) to the user instead of retrying itself.
- Small bugs: a 500 on draft approval, missing imports in tests, unstyled back buttons.
- Deployment: tried Google Cloud first (billing wasn't active), then Railway (trial expired), then put the frontend on Render when I wanted Vercel. Each time it needed me to fix an account or permission.

## Numbers

- **Tests:** 165 automated tests pass (guardrails, reply graph, mail flow, pipeline, API, LLM fallback chain). Ruff lint is clean.
- **Reply guardrails:** 12 tests on the reply graph, including: opt-out never reaches the LLM, a price in an LLM reply is blocked, low confidence hands off, picking a slot books it, an unknown slot hands off.
- **Qualifier eval:** 9 real companies (with their stored evidence) and the verdict a human would give. Before tuning, 4 of 9 verdicts were right. After tuning, 9 of 9. Run it with `cd backend && .venv/bin/python -m evals.qualifier_eval`. Be careful with this number: the set is small, I wrote the expected verdicts myself, and the same set was used to tune the prompt. It shows the direction, not real-world accuracy.
- **Pipeline so far (local runs):** 48 companies checked across 6 campaigns. 33 rejected with a stored reason (mostly "not a Shopify store" at the code-check step, then too big, too small, or not enough provable facts). 15 kept: 5 good, 7 maybe, 3 poor.
- **Cost:** $0. Free LLM tiers, free search tiers, free Resend, free Render and Vercel.

## Next steps

1. Run bigger campaigns to reach the 30+ qualified companies the brief asks for. The pipeline works; I ran small batches to stay inside free limits.
2. A larger, independent eval set for the qualifier, labeled by someone else, plus an eval for the email writer (facts cited, length, tone).
3. Compare the free models properly, and move the writer and reply agent to a stronger paid model if this becomes real.
4. A paid Render instance (or another host) to remove the cold start.
5. Book into the sales team's real calendar through the Cal.com API (`backend/app/services/calendar.py` is written so only `free_slots` and `book` change).
6. Roles and multiple users for the sales team, and a verified sending domain so test emails can go to any address.
