from __future__ import annotations

from typing import Literal, Dict, Any

from langgraph.graph import StateGraph, END

from agent.state import EmailState
from agent.triage_agent import triage
from agent.draft_agent import draft_reply


# ----------------------------
# Nodes
# ----------------------------

def node_triage(state: EmailState) -> EmailState:
    email = state["email"]
    result: Dict[str, Any] = triage(email)

    state.update(result)

    # Init loop controls
    state.setdefault("revision_count", 0)
    state.setdefault("max_revisions", 2)
    state.setdefault("feedback", None)
    state.setdefault("errors", [])
    state.setdefault("memory_notes", [])
    return state


def node_draft(state: EmailState) -> EmailState:
    email = state["email"]

    triage_result = {
        "department": state.get("department", "NeedsReview"),
        "confidence": float(state.get("confidence", 0.0)),
        "summary": state.get("summary", ""),
        "tags": state.get("tags", []),
    }

    state["draft"] = draft_reply(email, triage_result)
    return state


def node_apply_feedback(state: EmailState) -> EmailState:
    feedback = (state.get("feedback") or "").strip()
    if not feedback:
        return state

    # Inject feedback into the email body so the draft agent must obey it
    email = dict(state["email"])
    email["body"] = (
        email.get("body", "")
        + "\n\n---\nUSER FEEDBACK / REQUIRED CHANGES:\n"
        + feedback
    )

    triage_result = {
        "department": state.get("department", "NeedsReview"),
        "confidence": float(state.get("confidence", 0.0)),
        "summary": state.get("summary", ""),
        "tags": state.get("tags", []),
    }

    state["draft"] = draft_reply(email, triage_result)

    state["revision_count"] = int(state.get("revision_count", 0)) + 1
    state["feedback"] = None  # clear so we don't loop forever
    return state


def node_human_review(state: EmailState) -> EmailState:
    """
    CLI human review step:
    - If triage low confidence / NeedsReview: allow user to override department
    - Show draft and allow approve/revise/skip
    """
    email = state["email"]
    subject = email.get("subject", "(no subject)")
    sender = email.get("from", email.get("sender", "(unknown sender)"))

    print("\n" + "=" * 90)
    print(f"[HUMAN REVIEW] From: {sender}")
    print(f"[HUMAN REVIEW] Subject: {subject}")
    print("-" * 90)

    dept = state.get("department", "NeedsReview")
    conf = float(state.get("confidence", 0.0))

    # If unsure, ask user to correct department
    if dept == "NeedsReview" or conf < 0.55:
        print(f"[TRIAGE] department={dept} confidence={conf:.2f}")
        new_dept = input("Set department (Sales/Support/Finance/NeedsReview) or Enter to keep: ").strip()
        if new_dept:
            state["department"] = new_dept
            state["confidence"] = max(conf, 0.75)  # human override implies higher confidence
        print("-" * 90)

    draft = state.get("draft", "")
    if draft:
        print("[DRAFT]")
        print(draft)
        print("-" * 90)

        choice = input("Approve (a) / Revise (r) / Skip (s): ").strip().lower()

        if choice == "r":
            fb = input("Enter revision instructions (what to change): ").strip()
            state["feedback"] = fb
        elif choice == "s":
            state.setdefault("errors", []).append("Skipped by user.")
            # Clear draft to signal skip if you want
            # state["draft"] = ""

    return state


# ----------------------------
# Routers
# ----------------------------

def route_after_triage(state: EmailState) -> Literal["draft", "human_review"]:
    dept = state.get("department", "NeedsReview")
    conf = float(state.get("confidence", 0.0))

    # If unclear -> go to human review before drafting
    if dept == "NeedsReview" or conf < 0.55:
        return "human_review"

    return "draft"


def route_after_human(state: EmailState) -> Literal["apply_feedback", "end"]:
    # If user skipped, end
    errs = state.get("errors") or []
    if any("Skipped by user" in e for e in errs):
        return "end"

    feedback = (state.get("feedback") or "").strip()
    if not feedback:
        return "end"

    rev = int(state.get("revision_count", 0))
    max_rev = int(state.get("max_revisions", 2))
    if rev >= max_rev:
        state.setdefault("errors", []).append("Max revisions reached; returning last draft.")
        state["feedback"] = None
        return "end"

    return "apply_feedback"


# ----------------------------
# Build Graph
# ----------------------------

def build_graph():
    g = StateGraph(EmailState)

    g.add_node("triage", node_triage)
    g.add_node("draft", node_draft)
    g.add_node("human_review", node_human_review)
    g.add_node("apply_feedback", node_apply_feedback)

    g.set_entry_point("triage")

    # triage -> draft or human_review
    g.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "draft": "draft",
            "human_review": "human_review",
        },
    )

    # draft always goes to human review (approve/revise)
    g.add_edge("draft", "human_review")

    # human_review -> apply_feedback loop OR end
    g.add_conditional_edges(
        "human_review",
        route_after_human,
        {
            "apply_feedback": "apply_feedback",
            "end": END,
        },
    )

    # after applying feedback, we draft again (then human_review again)
    g.add_edge("apply_feedback", "draft")

    return g.compile()
