"""IntakeIQ conversation agent — a LangGraph state machine that drives one voice
turn: greeting -> qualifying -> scheduling -> confirming -> done.

The LLM never books blindly: booking only fires when the caller explicitly picks
one of the server-offered slots, and a dedicated graph node performs the booking.
"""

import os
import json
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from app import llm
from app.booking import generate_slots, make_ics, ics_data_url, BUSINESS_NAME

STAGES = ["greeting", "qualifying", "scheduling", "confirming", "done"]


class TurnState(TypedDict, total=False):
    messages: list        # [{role, content}]
    collected: dict       # name, reason, phone, email
    stage: str
    slots: list
    action: str           # none | offer_slots | book
    slot_id: str
    reply: str
    booking: dict
    usage: dict
    llm_ms: int


SYSTEM = """You are IntakeIQ, the friendly virtual receptionist for {biz}. You are on a live VOICE call, so every reply must be short, warm, and natural — 1-2 spoken sentences, no lists or markdown.

Your job, in order:
1. GREETING - greet the caller and ask how you can help.
2. QUALIFYING - collect the caller's full name, the reason for their visit, a phone number, and an email. Ask for what's missing one or two items at a time, conversationally.
3. SCHEDULING - once you have name, reason, and at least a phone OR email, you MUST offer the specific available slots below by saying their actual day and time out loud, then ask which one they'd like. Never say "let's get you scheduled" without naming the options.
4. CONFIRMING - when they pick a slot, recap (name, reason, slot) and confirm it's booked.

Known info so far: {collected}
Current stage: {stage}
Available appointment slots: {slots}

Return ONLY this JSON:
{{
 "reply": "<what you say next — spoken, 1-2 sentences>",
 "collected": {{"name":"","reason":"","phone":"","email":""}},
 "stage": "greeting|qualifying|scheduling|confirming|done",
 "action": "none|offer_slots|book",
 "slot_id": "<id of the slot the caller chose, else empty>"
}}
Rules: In "collected", always include everything known so far, updated with anything new the caller just said. Move to stage 'scheduling' with action 'offer_slots' once you have name + reason + (phone or email). Only set action 'book' with a real slot_id when the caller clearly picks one of the offered slots. Set stage 'done' after you confirm the booking. Never invent or assume a booking the caller did not confirm."""


def _slots_text(slots):
    return "; ".join(f"[{s['id']}] {s['label']}" for s in slots) or "(none yet)"


# ── nodes ─────────────────────────────────────────────────────────────────────
def n_ensure_slots(state: TurnState) -> TurnState:
    if not state.get("slots"):
        return {"slots": generate_slots()}
    return {}


def n_converse(state: TurnState) -> TurnState:
    collected = state.get("collected", {})
    slots = state["slots"]
    if llm.live():
        sys = SYSTEM.format(biz=BUSINESS_NAME, collected=json.dumps(collected),
                            stage=state.get("stage", "greeting"), slots=_slots_text(slots))
        data, usage, ms = llm.converse(sys, state["messages"])
    else:
        data, usage, ms = _mock_converse(state)
    merged = {**collected, **{k: v for k, v in (data.get("collected") or {}).items() if v}}
    return {
        "reply": data.get("reply", "Sorry, could you repeat that?"),
        "collected": merged,
        "stage": data.get("stage", state.get("stage", "greeting")),
        "action": data.get("action", "none"),
        "slot_id": data.get("slot_id", ""),
        "usage": usage,
        "llm_ms": ms,
    }


def n_book(state: TurnState) -> TurnState:
    slot = next((s for s in state["slots"] if s["id"] == state.get("slot_id")), None)
    if not slot:
        return {}
    c = state["collected"]
    booking = {
        "name": c.get("name", "Client"), "reason": c.get("reason", ""),
        "phone": c.get("phone", ""), "email": c.get("email", ""),
        "slot_id": slot["id"], "slot_label": slot["label"],
        "start": slot["start"], "end": slot["end"],
    }
    ics = make_ics(booking)
    booking["ics_url"] = ics_data_url(ics)
    return {"booking": booking, "stage": "done"}


def _route(state: TurnState) -> str:
    return "book" if state.get("action") == "book" and state.get("slot_id") else "end"


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        g = StateGraph(TurnState)
        g.add_node("ensure_slots", n_ensure_slots)
        g.add_node("converse", n_converse)
        g.add_node("book", n_book)
        g.add_edge(START, "ensure_slots")
        g.add_edge("ensure_slots", "converse")
        g.add_conditional_edges("converse", _route, {"book": "book", "end": END})
        g.add_edge("book", END)
        _graph = g.compile()
    return _graph


def process_turn(prior: dict, user_text: str) -> dict:
    messages = (prior.get("messages") or []) + [{"role": "user", "content": user_text}]
    state: TurnState = {
        "messages": messages,
        "collected": prior.get("collected", {}),
        "stage": prior.get("stage", "greeting"),
        "slots": prior.get("slots", []),
    }
    out = get_graph().invoke(state)
    out["messages"] = messages + [{"role": "assistant", "content": out["reply"]}]
    return out


# ── offline rule-based fallback ───────────────────────────────────────────────
def _mock_converse(state: TurnState):
    c = state.get("collected", {})
    last = state["messages"][-1]["content"] if state["messages"] else ""
    stage = state.get("stage", "greeting")
    reply, action, slot_id = "", "none", ""
    if stage == "greeting":
        reply = f"Hi, thanks for calling {BUSINESS_NAME}! May I have your full name and what the visit is for?"
        stage = "qualifying"
    elif not c.get("name"):
        c["name"] = last.strip().title()[:40]
        reply = "Thanks! And what's the reason for your visit?"
    elif not c.get("reason"):
        c["reason"] = last.strip()[:80]
        reply = "Got it. What's the best phone number and email to reach you?"
    elif not (c.get("phone") or c.get("email")):
        c["phone"] = "".join(ch for ch in last if ch.isdigit())[:15] or "555-0100"
        reply = f"Perfect. I have two openings: {state['slots'][0]['label']} or {state['slots'][1]['label']}. Which works?"
        stage, action = "scheduling", "offer_slots"
    else:
        pick = state["slots"][1] if "second" in last.lower() or "2" in last else state["slots"][0]
        slot_id, action, stage = pick["id"], "book", "confirming"
        reply = f"You're all set for {pick['label']}. I've booked it and sent your invite. Anything else?"
    return ({"reply": reply, "collected": c, "stage": stage,
             "action": action, "slot_id": slot_id}, {"in": 0, "out": 0}, 5)
