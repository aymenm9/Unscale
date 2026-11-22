# Ledgerwise AI SDR: rules for the AI coding tool (DRAFT, review before use)

## Project
Case study for Unscale (AI engineer role). An AI SDR platform for Ledgerwise, a fictional US bookkeeping firm for e-commerce brands.
Agent: Research → Qualify → Write → Reply → Book. A web app lets a non-technical sales team review and control everything.
The full brief is in BRIEFING.md. UX matters as much as the agent.

## Business rules (hard; every agent output must obey them)
1. Never quote a price or a price range. Pricing is discussed on a call.
2. Never state a fact about a company unless it is backed by a stored evidence item (url + quote).
3. stop / unsubscribe / "not interested" → add to the suppression list, never contact again, no reply except an optional confirmation.
4. "Are you a bot / AI?" → answer honestly.
5. If unsure (low confidence) → hand off to a human with a reason.

## Engineering rules
- The developer must understand every line. Keep code simple and explicit, no clever abstractions.
- Small commits with clear messages. Never commit secrets (.env* stays gitignored).
- Every LLM call returns structured output validated with a schema (zod).
- Guardrails are deterministic code first, LLM second.
- Every agent action is written to an audit log table.
- Outbound email goes ONLY to demo/test addresses (no real cold emails to real companies).
- Add an eval or test whenever reply or guardrail logic changes.
- Ask before adding a new paid service or dependency.
