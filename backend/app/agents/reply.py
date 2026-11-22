"""Reply agent: decides what to do with one inbound email.

Graph:  guard ──opt-out──────────────────────────────▶ suppress
          │
          ▼
        classify ──low confidence / human-only intent──▶ handoff
          │
          ▼
        draft ──▶ post_check ──price found / missing AI disclosure──▶ handoff (or fix)
                      │
                      ▼
                    send

The graph only DECIDES. It does not touch the database; app/services/replies.py applies
the decision (send, suppress, book, hand off) and writes the audit log. That keeps this
file easy to test with a fake LLM.
"""

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from app.agents import llm
from app.agents.prompts import REPLY_CLASSIFY, REPLY_WRITE
from app.config import settings
from app.guards import asks_if_bot, contains_price, is_opt_out

Intent = Literal[
    "question",  # asks about the service
    "objection",  # other pushback
    "wants_meeting",  # agrees to talk / asks for times
    "picked_time",  # chose one of the offered slots
    "pricing",  # asks how much it costs
    "bot_question",  # asks if we are an AI
    "not_now",  # interested later (may give a check-back date)
    "has_accountant",  # "we already have an accountant"
    "send_info",  # "send me some info"
    "opt_out",  # LLM's second opinion on rule 3
    "other",  # anything else (angry, legal, off-topic, out of office)
]

# Intents the agent never answers alone.
HUMAN_ONLY = {"other"}


class Analysis(BaseModel):
    intent: Intent
    also_asks_if_bot: bool = Field(description="True if the email also asks whether we are an AI")
    confidence: float = Field(ge=0, le=1, description="How sure you are about the intent")
    picked_slot_index: int | None = Field(
        default=None, description="If intent is picked_time: index of the chosen offered slot"
    )
    check_back_date: str | None = Field(
        default=None, description="If intent is not_now and they named a time: YYYY-MM-DD"
    )
    summary: str = Field(description="One sentence for the sales team")


class Reply(BaseModel):
    body: str = Field(description="Plain text email reply, under 120 words, no signature")
    offer_slots: bool = Field(description="True if the reply proposes call times")


class ReplyState(TypedDict, total=False):
    # input
    inbound: str
    history: str  # earlier messages, oldest first
    company_name: str
    contact_name: str
    offered_slots: list[str]  # human-readable slots already offered in this thread
    free_slots: list[str]  # free slots we can offer now
    strategy: str  # approved outreach strategy, as text
    # output
    action: Literal["suppress", "handoff", "send", "book"]
    reason: str
    analysis: dict
    reply: str
    slot_index: int | None


AI_DISCLOSURE = (
    "To be upfront: I'm an AI assistant working for the Ledgerwise team, "
    "and a person on the team reads these threads."
)


def guard(state: ReplyState) -> ReplyState:
    if is_opt_out(state["inbound"]):
        return {"action": "suppress", "reason": "Opt-out wording matched (deterministic rule)."}
    return {}


def classify(state: ReplyState) -> ReplyState:
    user = (
        f"OFFERED SLOTS (index: time): {list(enumerate(state.get('offered_slots', [])))}\n\n"
        f"<thread>\n{state.get('history', '')}\n</thread>\n\n"
        f"<email>\n{state['inbound']}\n</email>"
    )
    try:
        a = llm.structured(REPLY_CLASSIFY, user, Analysis, chain_names=settings.llm_judge)
    except llm.LLMNotConfigured:
        return {"action": "handoff", "reason": "LLM is not configured, a person must reply."}
    except Exception as e:  # invalid output, API error: never guess, hand off
        return {"action": "handoff", "reason": f"Classifier failed: {e}"}

    analysis = a.model_dump()
    if a.intent == "opt_out":
        return {
            "action": "suppress",
            "reason": "Classifier read this as an opt-out.",
            "analysis": analysis,
        }
    if a.confidence < settings.min_confidence:
        return {
            "action": "handoff",
            "reason": f"Low confidence ({a.confidence:.2f}) on intent '{a.intent}'.",
            "analysis": analysis,
        }
    if a.intent in HUMAN_ONLY:
        return {"action": "handoff", "reason": f"Needs a person: {a.summary}", "analysis": analysis}
    if a.intent == "picked_time":
        offered = state.get("offered_slots", [])
        if a.picked_slot_index is None or not (0 <= a.picked_slot_index < len(offered)):
            return {
                "action": "handoff",
                "reason": "Prospect picked a time that does not match an offered slot.",
                "analysis": analysis,
            }
        return {"action": "book", "slot_index": a.picked_slot_index, "analysis": analysis}
    return {"analysis": analysis}


def draft(state: ReplyState) -> ReplyState:
    must_disclose = asks_if_bot(state["inbound"]) or state["analysis"].get("also_asks_if_bot")
    user = (
        f"Prospect: {state.get('contact_name', '')} at {state.get('company_name', '')}\n"
        f"Intent: {state['analysis'].get('intent')}\n"
        f"APPROVED STRATEGY: {state.get('strategy', 'none yet')}\n"
        f"FREE SLOTS you may offer: {state.get('free_slots', [])}\n"
        f"Must say you are an AI: {bool(must_disclose)}\n\n"
        f"<thread>\n{state.get('history', '')}\n</thread>\n\n"
        f"<email>\n{state['inbound']}\n</email>"
    )
    try:
        r = llm.structured(REPLY_WRITE, user, Reply, chain_names=settings.llm_write)
    except Exception as e:
        return {"action": "handoff", "reason": f"Reply writer failed: {e}"}
    return {"reply": r.body}


def post_check(state: ReplyState) -> ReplyState:
    """Deterministic checks on what the LLM wrote, before anything is sent."""
    reply = state["reply"]
    if contains_price(reply):
        return {"action": "handoff", "reason": "Draft reply mentioned a price; blocked."}
    must_disclose = asks_if_bot(state["inbound"]) or state["analysis"].get("also_asks_if_bot")
    if must_disclose and " ai " not in f" {reply.lower()} ".replace(",", " ").replace(".", " "):
        reply = f"{AI_DISCLOSURE}\n\n{reply}"  # rule 4 is guaranteed by code, not by the prompt
    return {"action": "send", "reply": reply}


def _after_guard(state: ReplyState) -> str:
    return END if state.get("action") else "classify"


def _after_classify(state: ReplyState) -> str:
    return END if state.get("action") else "draft"


def _after_draft(state: ReplyState) -> str:
    return END if state.get("action") else "post_check"


def build_graph():
    g = StateGraph(ReplyState)
    g.add_node("guard", guard)
    g.add_node("classify", classify)
    g.add_node("draft", draft)
    g.add_node("post_check", post_check)
    g.set_entry_point("guard")
    g.add_conditional_edges("guard", _after_guard)
    g.add_conditional_edges("classify", _after_classify)
    g.add_conditional_edges("draft", _after_draft)
    g.add_edge("post_check", END)
    return g.compile()


reply_graph = build_graph()


def decide(state: ReplyState) -> ReplyState:
    """Run the graph on one inbound email and return the final state."""
    return reply_graph.invoke(state)
