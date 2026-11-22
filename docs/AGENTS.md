# Ledgerwise agents: the full list (draft for validation)

Each agent is one Python module in `backend/app/agents/`, with one job, typed input, and a pydantic-validated output.
"Code" means no LLM: deterministic Python. Guardrails run in code before and after every LLM call.

## The pipeline

```
Campaign settings
  -> 1 Search agent (LLM + tools)   plans keywords, runs searches, collects candidates
  -> code checks                    dedupe, US only, size, suppression   (cheap, certain)
  -> 2 Quick filter (Gemini Decision 1, decision model) keep/drop per company, with a reason
  -> 3 Researcher (LLM + tools)     reads pages, collects sourced facts
  -> 4 Qualifier (LLM)              good/maybe/poor, reasons for and against
  -> 5 Contact finder (last node)   right person + email, only for "good"
  -> 6 Email writer (LLM)           first email + follow-ups      -> HUMAN APPROVES
  -> 7 Reply agent (LLM)            answer, hand off, or book
     + thread report               updated by the Reply agent after every round
  -> 8 Compose assistant (LLM)      helps a human write
```

Every company that drops out writes a **Rejection** row: `company, stage, reason, evidence ids`.
The campaign page shows them in a "Not chosen" tab: where each one fell short and why.

## 1. Search agent (LLM with tools)
- **Job:** read the campaign (categories, channels, size, signals) and decide what to search. It writes its own keywords, runs a tool, looks at the results, and searches again until it has enough candidates.
- **Tools:** `search_web` (Tavily), `search_form_d` (SEC), `search_app_reviews` (Shopify App Store), `check_store` (`meta.json`).
- **Limits (code):** max 25 tool calls and max 300 Tavily credits per campaign; stop at the target count (about 3x the companies wanted).
- **Output:** `Candidate(name, domain, source_url, found_by_query)`.

## Code checks (no LLM)
- Duplicate domain, already contacted, suppressed: drop.
- `meta.json` says not US, or under 10 / over 2,000 products: drop.
- Why code: these are facts we can check for sure, so no LLM guess is needed and nothing is spent.

## 2. Quick filter (decision models: Gemini Decision 1, then Cloudflare Clef)

The decision model answers one typed choice question per company (keep / not_a_store / too_big /
outside_us / wrong_category) with a probability per option. Code drops a company only when
P(keep) < 0.25. Order: Gemini Decision 1 (Google Decisions API), then Clef, then the chat-model
filter below; if all fail, everyone is kept.

- **Job:** fast yes/no on each candidate from a small input: name, store data, homepage snippet. Removes the obvious misses (agencies, huge brands, wrong category) before the expensive research.
- **Batches:** 10 companies per call to stay under rate limits.
- **Rule:** when unsure, say yes. A wrong "no" is lost forever; a wrong "yes" only costs one research run.
- **Output:** `keep: bool`, `reason` (one line).

## 3. Researcher (LLM + fetch tools)
- **Job:** for one brand, read its pages (home, about, team, careers, wholesale, contact) plus 1 news search, then extract facts.
- **Output:** `Evidence(claim, quote, url)` list, plus `platform`, `channels`, `signals`.
- **Guardrail (code):** every `quote` must be an exact substring of the fetched page text, or the fact is dropped.

## 4. Qualifier (LLM)
- **Job:** judge each researched brand against the ICP and the campaign.
- **Output:** `verdict (good|maybe|poor)`, `score`, `reasons_for[]`, `reasons_against[]`, `revenue_band + confidence`, `employee_band + confidence`. Every reason cites evidence ids.
- **Guardrail (code):** reasons that cite unknown evidence ids are dropped; score = sum of reason points; confidence < 0.7 means `maybe` and a human looks.

## 5. Contact finder (last node, code + small LLM step)
- **Job:** find the founder, COO or finance lead and an email, only for `good` companies (saves Hunter credits).
- **Order:** Form D people, then the team/about page (LLM extracts name + title with a quote), then a published contact address, then an email pattern + MX check, then Hunter (top 30 only).
- **Output:** `Contact(name, title, email, email_confidence, source_url)`.
- **Guardrail (code):** a name without a source quote is dropped. No contact found: Rejection row with stage `contact`.

## The outreach strategy (what the human approves)
The human approves **one thing per company: the strategy plus the first email**. Not every email.
After that the agents work alone and only stop when they raise a hand.

`Strategy` (written by the Email writer, stored on the thread):
- `voice`: Peer Founder, Numbers-First Operator, Finance Peer (follow-ups use Short & Plain)
- `trigger`: the one sourced fact we open with (evidence id)
- `pain`: the bookkeeping problem we bet they have (e.g. "three payout streams to reconcile")
- `follow_up_angles`: one new angle per follow-up, each tied to evidence or a general e-commerce fact (e.g. 1: wholesale invoices and net-30; 2: sales tax after expansion; 3: polite last note)
- `avoid`: things not to mention for this company
- `goal`: book a 20-minute call

Follow-ups and replies are **generated when they are due**, from the strategy + the full thread, so they can react to what changed.

## 6. Email writer (LLM)
- **Job:** write the strategy and the first email. Later, write each follow-up on its due day from the approved strategy.
- **Rules:** 1 trigger fact, 50-90 words, subject 2-5 words, interest question as the CTA, no links.
- **Guardrails (code):** no price, word count, every `[n]` maps to stored evidence, banned phrases, no links. Fails go back to the LLM once with the errors, then to a human.
- **Fact checker (LLM, second pass):** checks every sentence against its evidence quote; anything unsupported blocks the draft with a reason.
- **Gate:** the human approves, edits or rejects the strategy + first email. Follow-ups that pass every check go out without a new approval.

## 7. Reply agent (LLM, exists today)
- **Job:** classify the reply, then send, suppress, hand off, schedule a check-back, or book.
- **Intents:** question, pricing, wants_meeting, picked_time, bot_question, has_accountant, not_now (stores a check-back date), send_info, objection, opt_out, other.
- **Auto mode:** sends on its own when confident and the reply passes the checks. Raises a hand (handoff with a reason) when unsure, angry, legal, an existing client, or "other".
- **Guardrails:** opt-out regex runs before the LLM; price check after; AI disclosure added if asked; follows the approved strategy.
- **Human takeover:** when a person writes in the thread, the agent stops. It only resumes when the person clicks "Hand back to agent".
- **Report:** at the end of every round it updates the thread report (see 8).

## 7b. Thread report (part of the Reply agent, not a separate agent)
- After every round (inbound or outbound) the same agent rewrites "What we know": interest, pain, objections, next step, what is new.
- When a call is booked, the report adds call prep.
- Facts about the company must cite evidence ids.

## 8. Compose assistant (LLM)
- **Page:** write the email on the left, live preview of the real HTML on the right, "Rewrite with AI" button.
- **Rewrite with AI:** opens a comment box ("warmer", "mention their Amazon launch"). The rewriter gets the full details: company, evidence, strategy, the whole thread, the report.
- **Templates:** hard-coded in Python (pricing question, has an accountant, too busy, send info, booking confirmation).
- **Guardrail:** the same checks run before send. The human always clicks send.

## Follow-up timer (code, no LLM)
- Checks every 15 minutes. Follow-up 1 on day 3, 2 on day 7, 3 on day 11, weekdays only, 9am-12pm in the prospect's time zone.
- Asks the Email writer for the next follow-up from the strategy, runs the checks, sends through the email sender.
- Stops for good when they reply, opt out, book, or a human takes over. A "not now" reply sets a check-back date instead.

## Email sender service (code, the only way out)
Every email from any agent or human goes through one function, `send_email()`. Before sending it checks:
1. Recipient or domain is not on the do-not-contact list.
2. Thread is not closed, suppressed, or booked (for follow-ups).
3. Recipient is rewritten to the demo inbox (project rule: no real cold emails).
4. Not more than 1 email to the same person per 24 hours, and a daily cap for the whole account.
5. Draft checks passed (no price, citations valid).
It adds the unsubscribe footer and headers, stores the message, and writes the audit log. A block is logged with the reason.

## Test inbox (simulation)
- A page in the app that shows every email the agents "sent" to demo prospects, rendered like a real inbox.
- The user can reply as the prospect. The reply goes through the exact same code path as a real inbound email.
- Real email too: Resend gives a free receiving address (`anything@<id>.resend.app`) and an `email.received` webhook. We set Reply-To to `reply+<thread>@<id>.resend.app`, so a real reply (e.g. from your own Gmail) reaches the agent. The test inbox works without any keys.

## Not agents (shared code)
- `guards/`: deterministic checks used by every agent.
- `llm.py`: the free provider chain (Groq, OpenCode, AxForge, Gonka) with schema validation and one retry.
- `audit.log()`: every agent action is written to the audit table.

## Open choices
1. Quick filter model: Gemini Decision 1 (decision model), then Cloudflare Clef-flash. Last fallback: Gemini Flash Lite (Gemma 4 returned 503s in testing).

## Models per job (rotating pools)

Every LLM call names a job. Each job has its own pool of free models; calls rotate inside
the pool, and a model that hits a rate limit rests until its cooldown ends. Set in `.env`.

| Job | Used by | Pool |
|---|---|---|
| fast | search agent, brand extraction | Groq gpt-oss-20b, Gemini 3.5 Flash Lite, Cloudflare gpt-oss-20b |
| decision | quick filter | Gemini Decision 1, then Cloudflare Clef-flash (decision models); last fallback Gemini 3.5 Flash Lite, Cloudflare gpt-oss-20b |
| read | researcher, contact finder | Gemini 2.5 Flash (long context), Cloudflare gpt-oss-120b |
| judge | qualifier, reply classifier, thread report | Groq + Cloudflare gpt-oss-120b |
| write | first email, follow-ups, replies, AI rewrite | Groq + Cloudflare gpt-oss-120b |
| check | fact checker | Gemini 2.5 Flash, Groq Qwen3 (a different family from the writer) |

OpenCode Zen's free models only work inside the OpenCode app, not through its API, so it is
configured but left out (empty model).
