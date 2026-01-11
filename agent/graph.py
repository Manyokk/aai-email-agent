from __future__ import annotations

from typing import Literal, Dict, Any

from langgraph.graph import StateGraph, END

from agent.state import EmailState
from agent.triage_agent import triage
from agent.draft_agent import draft_reply

from memory.store import (
    load_memory,
    save_memory,
    get_sender_department,
    set_sender_department,
    get_department_tone,
)

ALLOWED_DEPARTMENTS = {"Sales", "Support", "Finance", "NeedsReview"}


# ----------------------------
# Nodes: Memory
# ----------------------------

def node_load_memory(state: EmailState) -> EmailState:
    path = state.get("memory_path", "memory/memory_store.json")
    state["memory_path"] = path
    state["memory"] = load_memory(path)
    state.setdefault("used_sender_override", False)
    return state


def node_apply_memory(state: EmailState) -> EmailState:
    """
    Apply memory BEFORE triage/draft:
    - If sender has known department -> override department, boost confidence
    - Set tone based on department
    """
    mem = state.get("memory") or {}
    email = state["email"]
    sender = email.get("from", email.get("sender", "")) or ""

    remembered_dept = get_sender_department(mem, sender)
    if remembered_dept:
        state["department"] = remembered_dept
        state["confidence"] = max(float(state.get("confidence", 0.0)), 0.85)
        state["used_sender_override"] = True

    dept = state.get("department", "NeedsReview")
    tone = get_department_tone(mem, dept)
    if tone:
        state["tone"] = tone

    return state


def node_save_memory(state: EmailState) -> EmailState:
    mem = state.get("memory")
    path = state.get("memory_path")
    if mem and path:
        save_memory(path, mem)
    return state


# ----------------------------
# Nodes: Core
# ----------------------------

def node_triage(state: EmailState) -> EmailState:
    email = state["email"]

    # If memory already set a department, skip triage for department decision
    # (triage can still provide summary/tags if your triage() returns them
    # but we keep it minimal and safe here)
    if not state.get("department"):
        result: Dict[str, Any] = triage(email)
        state.update(result)

    state.setdefault("revision_count", 0)
    state.setdefault("max_revisions", 2)
    state.setdefault("feedback", None)
    state.setdefault("errors", [])
    return state


def node_draft(state: EmailState) -> EmailState:
    email = state["email"]

    triage_result = {
        "department": state.get("department", "NeedsReview"),
        "confidence": float(state.get("confidence", 0.0)),
        "summary": state.get("summary", ""),
        "tags": state.get("tags", []),
        "tone": state.get("tone", None),
    }

    tone = state.get("tone")
    if tone:
        email = dict(email)
        email["body"] = (email.get("body", "") + f"\n\n---\nTONE REQUIREMENT:\n{tone}\n")

    state["draft"] = draft_reply(email, triage_result)
    return state


def node_apply_feedback(state: EmailState) -> EmailState:
    feedback = (state.get("feedback") or "").strip()
    if not feedback:
        return state

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
        "tone": state.get("tone", None),
    }

    state["draft"] = draft_reply(email, triage_result)
    state["revision_count"] = int(state.get("revision_count", 0)) + 1
    state["feedback"] = None
    return state


def node_human_review(state: EmailState) -> EmailState:
    """
    CLI human review:
    - Validate department input before applying and before saving to memory
    - Show draft and allow approve/revise/skip
    - Save sender->department ONLY if department is valid
    """
    email = state["email"]
    subject = email.get("subject", "(no subject)")
    sender = email.get("from", email.get("sender", "(unknown sender)")) or "(unknown sender)"

    print("\n" + "=" * 90)
    print(f"[HUMAN REVIEW] From: {sender}")
    print(f"[HUMAN REVIEW] Subject: {subject}")
    print("-" * 90)

    dept = state.get("department", "NeedsReview")
    conf = float(state.get("confidence", 0.0))

    # If unsure, allow correction
    if dept == "NeedsReview" or conf < 0.55:
        print(f"[TRIAGE] department={dept} confidence={conf:.2f}")
        new_dept = input("Set department (Sales/Support/Finance/NeedsReview) or Enter to keep: ").strip()

        if new_dept:
            if new_dept not in ALLOWED_DEPARTMENTS:
                print(f"[WARN] Invalid department '{new_dept}'. Keeping '{dept}'.")
            else:
                state["department"] = new_dept
                state["confidence"] = max(conf, 0.75)

        print("-" * 90)

    # Show draft (if exists)
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

    # MEMORY WRITE (safe): remember sender -> department if valid
    mem = state.get("memory")
    final_dept = (state.get("department") or "").strip()
    if mem and sender and final_dept in ALLOWED_DEPARTMENTS and final_dept != "NeedsReview":
        set_sender_department(mem, sender, final_dept)

    return state


# ----------------------------
# Routers
# ----------------------------

def route_after_triage(state: EmailState) -> Literal["draft", "human_review"]:
    dept = state.get("department", "NeedsReview")
    conf = float(state.get("confidence", 0.0))

    if dept == "NeedsReview" or conf < 0.55:
        return "human_review"
    return "draft"


def route_after_human(state: EmailState) -> Literal["apply_feedback", "save_and_end"]:
    errs = state.get("errors") or []
    if any("Skipped by user" in e for e in errs):
        return "save_and_end"

    feedback = (state.get("feedback") or "").strip()
    if not feedback:
        return "save_and_end"

    rev = int(state.get("revision_count", 0))
    max_rev = int(state.get("max_revisions", 2))
    if rev >= max_rev:
        state.setdefault("errors", []).append("Max revisions reached; returning last draft.")
        state["feedback"] = None
        return "save_and_end"

    return "apply_feedback"


# ----------------------------
# Build Graph
# ----------------------------

def build_graph():
    g = StateGraph(EmailState)

    g.add_node("load_memory", node_load_memory)
    g.add_node("apply_memory", node_apply_memory)
    g.add_node("save_memory", node_save_memory)

    g.add_node("triage", node_triage)
    g.add_node("draft", node_draft)
    g.add_node("human_review", node_human_review)
    g.add_node("apply_feedback", node_apply_feedback)

    g.set_entry_point("load_memory")

    g.add_edge("load_memory", "apply_memory")
    g.add_edge("apply_memory", "triage")

    g.add_conditional_edges(
        "triage",
        route_after_triage,
        {"draft": "draft", "human_review": "human_review"},
    )

    g.add_edge("draft", "human_review")

    g.add_conditional_edges(
        "human_review",
        route_after_human,
        {"apply_feedback": "apply_feedback", "save_and_end": "save_memory"},
    )

    g.add_edge("apply_feedback", "draft")
    g.add_edge("save_memory", END)

    return g.compile()
