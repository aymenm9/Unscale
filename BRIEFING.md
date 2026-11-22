# Unscale AI Engineer case: briefing

Prepared 2026-11-19 while you were away. No app code written yet.

## 1. What they want, in one paragraph

Build and **deploy** an "AI SDR" (AI sales rep) platform for **Ledgerwise**, a made-up US bookkeeping firm that sells to e-commerce brands. An AI agent must **Research → Qualify → Write → Reply → Book calls**. The sales team (not technical) uses a web app to check and approve everything. The doc says **UX counts as much as the agent**. They expect about 2 days of work. **The 72h timer started when you requested access to the doc.**

## 2. Requirements checklist (straight from the doc)

**Agent**
- [ ] Research: **≥30 real companies** that fit the ICP (US e-com, Shopify/Amazon/own site, $1–10M revenue, 5–50 staff). Contact = founder / COO / head of finance.
- [ ] Signals to look for: hiring in finance/ops, recently raised money, moving into new channels (wholesale, Amazon, retail, new countries).
- [ ] Qualify: a score **plus reasons, each with a source** (link + quote).
- [ ] Write: a short, personal first email. **Every fact must come from the research.**
- [ ] Reply: answer questions, handle objections, follow the rules, hand off to a human.
- [ ] Book: offer **real free slots** and book the call in a real calendar.

**The rules (they will test these)**
1. Never quote a price.
2. Never state anything that isn't true. Every fact needs a source.
3. stop / unsubscribe / "not interested" → stop forever (suppression list).
4. "Are you a bot?" → answer honestly.
5. Not sure → send to a human.

**Platform (for the sales team)**
- [ ] Companies, with score and reasons (and their sources)
- [ ] Email review: approve / edit / reject
- [ ] Every conversation, with "take over thread"
- [ ] Booked calls

**What to send**
- [ ] Live URL plus a login, **online for 2 weeks**
- [ ] Public GitHub repo
- [ ] **Full, unedited AI session exports** (`/export` in every Claude Code session. **This session counts**, so export it too.)
- [ ] `HOW_I_WORKED.md`: tools for each step and why, the plan and how it changed, rules given to the AI, where the AI got things wrong, **accuracy numbers**, cost, next steps
- [ ] Loom, max 10 min, presented **as if to the Ledgerwise sales team**

> They say "you must know every detail" and "we look at how well you direct the AI". So the process (plan, CLAUDE.md, evals, catching AI mistakes) counts as much as the code. Write down AI mistakes as they happen; HOW_I_WORKED needs them.

## 3. What already exists online

- **vercel-labs/lead-agent**: Next.js + AI SDK + Workflow DevKit. Research → qualify (`generateObject`) → draft → human approval in Slack → send. Closest reference architecture for the first half. It has no reply handling and no booking. ([template](https://vercel.com/templates/next.js/lead-processing-agent))
- **AgentSDR (Kandid)**: open-source outbound workspace; an AI CRM reads replies and drafts answers. ([info](https://chatgate.ai/post/agentsdr))
- Others: ZeroGTM, OpenOutreach, "AI Sales Team for Claude Code" ([roundup](https://syncgtm.com/blog/ai-lead-generation-agent-github)). **None of them books calls**, so booking plus strict rule-following is where you can stand out.
- Lessons from reply-handling posts: replies can carry **several labels** ("not me, try Ana, and take me off your list" is a referral and an unsubscribe). Treat unsubscribe as a **legal signal**. Act only on high confidence; everything else goes to a human. ([reply.io](https://how.reply.io/learn/reply-classification), [firstsales](https://firstsales.io/blog/ai-reply-misclassification/), [Unify eval guide](https://www.unifygtm.com/explore/ai-sdr-objection-handling-evaluation))

## 4. Suggested stack (all free tier except the LLM)

| Step | Tool | Why |
|---|---|---|
| App + hosting | **Next.js (TS) + shadcn/ui on Vercel** | Free, deploys fast, stays up 2 weeks, good-looking UI quickly |
| DB + login | **Supabase** (Postgres + Auth) | Free, one demo login. ⚠️ Free projects **pause after ~1 week idle**, so add a daily Vercel cron ping (or use Neon) |
| Find companies | **Exa search API** (semantic: "Shopify DTC brand hiring bookkeeper") | Built for "find companies like X". Free tier ([pricing notes](https://crustdata.com/reviews/exa)) |
| Read sites | **Firecrawl** scrape (1,000 free credits/month) | Turns company sites, about pages and job pages into clean text for citations ([pricing](https://www.firecrawl.dev/pricing)) |
| Hiring signal | **Greenhouse / Lever / Ashby public job-board JSON** | Free, no key, gives real proof links |
| Funding / channels | Exa news search + the company's own site | Gives quotable sources |
| Contact | Founder name from the About page / LinkedIn search result; email via **Hunter free** or marked "unverified" | Be honest about confidence |
| LLM | **Claude** (stronger model for writing and replies, small model for classifying) | Best at following rules and returning structured output. Costs a few dollars. **Gemini free tier** is the zero-cost backup |
| Email | **Resend** send + **inbound webhook** for replies | Real threads end to end ([inbound docs](https://resend.com/docs/dashboard/inbound/introduction)). Check the free-plan inbound limits |
| Booking | **Cal.com API v2**: `GET /v2/slots`, `POST /v2/bookings` | Real free slots and real bookings, simple API. Google Calendar freebusy is the backup |

## 5. Agent design (the part they will grill you on)

- **One evidence store**: each research fact = `{claim, quote, url, fetched_at}`. Qualify and Write may only point to evidence IDs. **No ID = the claim isn't allowed.**
- **Checker after writing** (code + LLM): every sentence in an email must map to evidence. Check for any `$` or price words. Fail = rewrite or send to a human.
- **Reply pipeline**: (1) code check for unsubscribe/stop words → suppress at once; (2) LLM multi-label classification with confidence; (3) route: answer / offer slots / hand off / suppress; (4) check the draft again (no price, no made-up facts, honest about being AI).
- **Confidence threshold** → "Needs human" queue that shows the reason.
- **Human-in-the-loop** first emails are always approved by a person. Replies: auto-send only on high confidence (with a per-company toggle), otherwise draft for review.
- **Audit log** of every agent action (good to show in the Loom, and builds trust).

## 6. Evals (gives you the "numbers" HOW_I_WORKED asks for)

- **Reply test set of about 40 to 60** made-up replies: question, objection, price ask, bot ask, unsubscribe (including hidden ones), meeting request, a time that doesn't work, out of office, referral, angry, unclear. Expected action for each. Report "x/N correct", plus **0 price leaks, 0 missed unsubscribes** as hard checks.
- **Grounding check** on all 30+ emails: % of claims backed by a real, working source (spot-check by hand too).
- **Qualification check**: label ~10 companies by hand, then compare with the agent's scores.

## 7. Key risks and decisions for you

1. **Don't cold-email real companies.** Research real companies, but have "send" go to **your own test addresses** (show the real contact in the UI next to a "demo routing" label). Real-looking, but no spam and no legal risk. ← my strong advice
2. **LLM cost**: Claude (a few $, better quality) or Gemini free?
3. **Deadline**: when did you request access? Everything gets planned around that.
4. Revenue ($1–10M) can't be checked for private companies. Estimate it from signals and **say it's an estimate, with a confidence level.** Being honest about this fits rule 2.

## 8. Rough 2-day plan

- **Day 1 AM**: repo, CLAUDE.md, schema, auth, deploy an empty app (get it live early)
- **Day 1 PM**: research + qualify pipeline → 30+ companies with sources in the DB; Companies UI
- **Day 2 AM**: email drafting + review queue; Resend send/inbound; reply agent + conversations UI + takeover
- **Day 2 PM**: Cal.com booking + Calls page; evals; polish UI
- **Day 3 (buffer)**: HOW_I_WORKED, Loom, exports, check that everything stays online

## 9. Setup done / your to-do

**Done by me**
- Read the whole case doc (all 1 tab, no comments)
- Installed **GitHub CLI** to `~/.local/bin/gh` (v2.105.0)
- `git init` in this folder and wrote a draft **`CLAUDE.md`** (rules for the AI coding tool, which HOW_I_WORKED asks about)

**You need to do (accounts and keys can't be made for you)**
- [ ] `gh auth login`, then I create the **public** repo
- [ ] Accounts and API keys: Vercel, Supabase, Anthropic (or Gemini), Exa, Firecrawl, Resend (+ a domain or subdomain for inbound), Cal.com, optionally Hunter
- [ ] In claude.ai → Connectors, enable: **Vercel, Supabase, Exa, Firecrawl** (all in the registry; they let me test research queries and manage deploys/DB during development). Optional: Google Calendar
- [ ] Skills already available and useful: `superpowers:brainstorming` / `writing-plans` / `test-driven-development`, `frontend-design`, `claude-api`, built-in browser for UI checks
