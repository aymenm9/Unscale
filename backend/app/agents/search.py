"""Search agent: an LLM that picks tools and keywords until it has enough candidates.

Each turn the LLM returns a SearchStep (validated JSON): which tool to call, with what
input, plus the brands it saw in earlier results. Code runs the tool, checks the budget,
and only keeps brands that really appear in a tool result.
No native "function calling" is needed, so it works on every free provider.
"""

import json
import logging

import httpx

from app.agents import llm
from app.agents.prompts import CANDIDATE_EXTRACT, SEARCH_AGENT
from app.agents.schemas import Candidate, CandidateList, SearchStep
from app.config import settings
from app.guards.research import BudgetExceeded, ToolBudget, clean_domain, seen_in_results
from app.tools import appstore, sec, shopify, web
from app.tools.http import Blocked

log = logging.getLogger(__name__)

TOOLS_HELP = (
    """\
TOOLS (pick one per step):
- search_web(query): web search, costs 1 credit. Good for news and brand sites.
- search_form_d(query): SEC Form D filings (recent private fundraises) matching keywords.
  Gives company names and states, no domain: find the domain with search_web next.
- read_app_reviews(app, page): Shopify App Store reviews. Reviewers are real stores.
  Useful apps: """
    + ", ".join(f"{k} ({v})" for k, v in appstore.SIGNAL_APPS.items())
    + """
- check_store(domain): confirms a Shopify store and returns its country and product count.
- finish: stop searching.
"""
)


def run_tool(step: SearchStep, budget: ToolBudget) -> str:
    """Run one tool and return a short text result for the LLM to read."""
    if step.tool == "search_web":
        budget.spend("search_web", credits=1)
        try:
            results = web.search(step.query or "")
        except web.SearchNotConfigured:
            return "search_web is not available (no API key). Use the other tools."
        return "\n".join(f"- {r['title']} | {r['url']} | {r['snippet'][:300]}" for r in results)
    if step.tool == "search_form_d":
        budget.spend("search_form_d")
        rows = sec.search_form_d(step.query or "")
        return (
            "\n".join(
                f"- {r['name']} | state {r['state']} | filed {r['filed']} | {r['url']}"
                for r in rows
            )
            or "No filings found."
        )
    if step.tool == "read_app_reviews":
        budget.spend("read_app_reviews")
        text = appstore.read_reviews(step.app or "shipbob", step.page or 1)
        return text or "Could not read that page."
    if step.tool == "check_store":
        budget.spend("check_store")
        meta = shopify.check_store(clean_domain(step.domain or ""))
        return json.dumps(meta) if meta else "Not a Shopify store (no /meta.json)."
    return ""


MAX_STEPS_WITHOUT_NEW = 6  # stop when several searches in a row add nothing


def extract_candidates(campaign: dict, block: str) -> list[Candidate]:
    """A small separate LLM call: which brands are in this one tool result?"""
    user = f"CAMPAIGN: {json.dumps(campaign)}\n\n<search_results>\n{block}\n</search_results>"
    try:
        return llm.structured(
            CANDIDATE_EXTRACT, user, CandidateList, chain_names=settings.llm_fast
        ).candidates
    except Exception as e:
        log.warning("candidate extraction failed: %s", e)
        return []


def find_candidates(
    campaign: dict, target: int, budget: ToolBudget, on_step=None
) -> tuple[list, list[str]]:
    """Returns (candidates, a readable log of every step).
    on_step(text, found_count) is called after each step (progress, and a place to stop)."""
    transcript: list[str] = []  # what the LLM sees: its steps and the tool results
    observations = ""  # all tool results, used to check candidates are real
    found: dict[str, Candidate] = {}
    steps_log: list[str] = []
    done_calls: set[str] = set()
    steps_without_new = 0

    def add(cands: list[Candidate]) -> int:
        added = 0
        for c in cands:
            d = clean_domain(c.domain)
            if d and d not in found and seen_in_results(c.name, d, observations):
                found[d] = c.model_copy(update={"domain": d})
                added += 1
            elif d and d not in found:
                steps_log.append(f"Ignored {c.name}: not seen in any tool result.")
        return added

    while len(found) < target:
        user = (
            f"CAMPAIGN: {json.dumps(campaign)}\nTARGET: {target} candidates\n"
            f"FOUND SO FAR ({len(found)}): {', '.join(found) or 'none'}\n"
            f"BUDGET LEFT: {budget.max_calls - budget.calls} tool calls, "
            f"{budget.max_credits - budget.credits} search credits\n\n{TOOLS_HELP}\n"
            "<search_results>\n" + "\n\n".join(transcript[-6:]) + "\n</search_results>"
        )
        try:
            step = llm.structured(SEARCH_AGENT, user, SearchStep, chain_names=settings.llm_fast)
        except Exception as e:
            steps_log.append(f"Stopped: the model failed ({e}).")
            break

        add(step.new_candidates)

        if step.tool == "finish":
            steps_log.append(f"Finished: {step.thought}")
            break
        what = step.query or step.app or step.domain or ""
        key = f"{step.tool}:{what.strip().lower()}:{step.page or 1}"
        if key in done_calls:
            result = "You already ran exactly this. Use different keywords or another tool."
        else:
            done_calls.add(key)
            try:
                result = run_tool(step, budget)
            except BudgetExceeded as e:
                steps_log.append(f"Stopped: {e}")
                break
            except (httpx.HTTPError, Blocked) as e:
                # One slow or broken site must not end the campaign: tell the model and go on.
                log.warning("search tool %s failed: %s", step.tool, e)
                result = f"The tool failed ({type(e).__name__}). Try another query or tool."
        block = f"[{step.tool} {what}]\n{result[:3500]}"
        transcript.append(block)
        observations += "\n" + block
        added = add(extract_candidates(campaign, block)) if step.tool != "check_store" else 0
        steps_log.append(f"{step.tool}({what}): {step.thought} (+{added} brands)")
        steps_without_new = 0 if added else steps_without_new + 1
        if on_step:
            on_step(f"{step.tool.replace('_', ' ')}: {what}"[:120], len(found))
        if steps_without_new >= MAX_STEPS_WITHOUT_NEW:
            steps_log.append(
                f"Stopped: {MAX_STEPS_WITHOUT_NEW} searches in a row found nothing new."
            )
            break

    return list(found.values())[: target * 2], steps_log
