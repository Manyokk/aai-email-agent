from __future__ import annotations

import os
import re
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from agent.state import EmailState
from agent.draft_agent import draft_reply
from config.loader import (
    load_company_config,
    dept_id_to_name,
    dept_id_to_tone,
    alias_to_department,
    employees_by_department,
    fallback_employee_email,
)


# ----------------------------
# Helpers
# ----------------------------

def _get_to_addresses(email: Dict[str, Any]) -> str:
    to_val = email.get("to") or email.get("recipient") or email.get("email_to") or ""
    if isinstance(to_val, list):
        return " ".join([str(x) for x in to_val])
    return str(to_val)


def llm_route_department(cfg: Dict[str, Any], email: Dict[str, Any]) -> Dict[str, Any]:
    dept_ids = [
        str(d.get("id"))
        for d in (cfg.get("departments", []) or [])
        if isinstance(d, dict) and d.get("id")
    ]
    dept_ids = [d.strip().lower() for d in dept_ids if d and d.strip()]
    if not dept_ids:
        return {"department_id": "needs_review", "confidence": 0.40}

    allowed = dept_ids + ["needs_review"]

    subject = str(email.get("subject") or "")
    body = str(email.get("body") or email.get("text") or "")
    sender = str(email.get("from") or email.get("sender") or "")
    to_line = _get_to_addresses(email)

    blob = f"FROM: {sender}\nTO: {to_line}\nSUBJECT: {subject}\nBODY:\n{body}"

    system = (
        "You route incoming emails to a department for ONE company.\n"
        "Return ONLY the best department_id from the allowed list. No extra words.\n\n"
        f"ALLOWED: {allowed}\n"
    )

    try:
        llm = ChatOllama(
            model=os.getenv("AAI_ROUTER_MODEL", "llama3.2"),
            temperature=0.0,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=blob)])
        raw = (resp.content or "").strip().strip('"').strip("'").lower()

        if raw in allowed:
            conf = 0.65 if raw != "needs_review" else 0.45
            return {"department_id": raw, "confidence": conf}

        return {"department_id": "needs_review", "confidence": 0.45}
    except Exception:
        return {"department_id": "needs_review", "confidence": 0.40}


def route_department(cfg: Dict[str, Any], email: Dict[str, Any]) -> Dict[str, Any]:
    # 1) Alias routing
    dept_map = alias_to_department(cfg)
    to_text = _get_to_addresses(email).lower()
    for addr, dep_id in (dept_map or {}).items():
        if str(addr).lower() in to_text:
            return {"department_id": str(dep_id).lower(), "confidence": 0.95}

    # 2) Keyword routing
    body = (email.get("body") or email.get("text") or "").lower()
    subject = (email.get("subject") or "").lower()
    blob = subject + "\n" + body

    rules = (cfg.get("routing_rules", {}) or {}).get("keyword_to_department", []) or []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        dep_id = str(rule.get("department_id") or "").strip().lower()
        if not dep_id:
            continue
        for kw in (rule.get("keywords") or []):
            kw_s = str(kw).strip().lower()
            if kw_s and kw_s in blob:
                return {"department_id": dep_id, "confidence": 0.75}

    # 3) LLM fallback
    return llm_route_department(cfg, email)


def assign_owner(cfg: Dict[str, Any], dept_id: str, rr_state: Dict[str, int]) -> Dict[str, str]:
    emps_by_dep = employees_by_department(cfg) or {}
    candidates = emps_by_dep.get(dept_id, []) or []

    # Fallback employee
    fb = (fallback_employee_email(cfg) or "").strip().lower()

    if not candidates:
        # Try fallback employee details from cfg["employees"]
        if fb:
            for emp in (cfg.get("employees") or []):
                if str(emp.get("email", "")).strip().lower() == fb:
                    return {
                        "owner_email": fb,
                        "signature": str(emp.get("signature") or "").strip(),
                    }
            return {"owner_email": fb, "signature": ""}
        return {"owner_email": "", "signature": ""}

    idx = int(rr_state.get(dept_id, 0))
    chosen = candidates[idx % len(candidates)]
    rr_state[dept_id] = (idx + 1) % len(candidates)

    return {
        "owner_email": str(chosen.get("email") or "").strip().lower(),
        "signature": str(chosen.get("signature") or "").strip(),
    }


# ----------------------------
# Nodes
# ----------------------------

def node_load_config(state: EmailState) -> EmailState:
    path = state.get("config_path", "config/company_config.json")
    state["config_path"] = path
    state["config"] = load_company_config(path)

    # Defaults (safe)
    state.setdefault("errors", [])
    state.setdefault("revision_count", 0)
    state.setdefault("max_revisions", int(state.get("max_revisions", 3) or 3))
    state.setdefault("approved", False)
    state.setdefault("skipped", False)
    state.setdefault("feedback", None)

    # IMPORTANT: internal rr state
    state.setdefault("_rr_state", {})
    return state


def node_route_and_assign(state: EmailState) -> EmailState:
    cfg = state["config"]
    email = state["email"]

    routed = route_department(cfg, email)
    dept_id = str(routed.get("department_id") or "needs_review").strip().lower() or "needs_review"

    state["department_id"] = dept_id
    state["confidence"] = float(routed.get("confidence") or 0.0)

    tones = dept_id_to_tone(cfg) or {}
    default_tone = ((cfg.get("company") or {}).get("default_tone") or "").strip()
    state["tone"] = tones.get(dept_id) or (default_tone if default_tone else None)

    rr_state = state.get("_rr_state", {}) or {}
    assigned = assign_owner(cfg, dept_id, rr_state)

    state["_rr_state"] = rr_state
    state["owner_email"] = assigned.get("owner_email", "")
    state["signature"] = assigned.get("signature", "")
    return state


def node_draft(state: EmailState) -> EmailState:
    cfg = state["config"]
    dept_names = dept_id_to_name(cfg) or {}
    dept_name = dept_names.get(state.get("department_id", ""), state.get("department_id", "needs_review"))

    email = dict(state["email"])
    tone = state.get("tone")
    sig = state.get("signature")

    # Inject constraints into the email body so draft_agent can follow them
    constraints = []
    constraints.append(f"DEPARTMENT: {dept_name}")
    if tone:
        constraints.append(f"TONE: {tone}")
    if state.get("owner_email"):
        constraints.append(f"RESPONDER: {state['owner_email']}")
    if sig:
        constraints.append("SIGNATURE (use exactly at end):\n" + sig)

    email["body"] = (email.get("body") or "") + "\n\n---\n" + "\n\n".join(constraints) + "\n"

    # draft_reply signature: draft_reply(email, triage_result)
    state["draft"] = draft_reply(email, {"department": dept_name, "confidence": state.get("confidence", 0.0)})
    return state


def node_chat_review(state: EmailState) -> EmailState:
    interactive = os.getenv("AAI_INTERACTIVE", "1").strip().lower() not in {"0", "false", "no"}

    if not interactive:
        state["approved"] = True
        return state

    email = state["email"]
    cfg = state["config"]
    dept_names = dept_id_to_name(cfg) or {}
    dept_name = dept_names.get(state.get("department_id", ""), state.get("department_id", "needs_review"))

    sender = email.get("from") or email.get("sender") or "(unknown sender)"
    subject = email.get("subject") or "(no subject)"

    print("\n" + "=" * 90)
    print(f"[CHAT REVIEW] From: {sender}")
    print(f"[CHAT REVIEW] Subject: {subject}")
    print(f"[ROUTED] Department: {dept_name} | Owner: {state.get('owner_email','')}")
    print("-" * 90)
    print(state.get("draft", ""))
    print("-" * 90)

    print("You can review or refine this draft however you like.\n")
    print("• Type 'approve' (or 'a') to accept and move on")
    print("• Type 'skip' (or 's') to leave it unchanged")
    print("• Or just tell me what you want changed (tone, length, wording, add/remove lines, etc.)\n")
    print("I’m here to help.\n")

    while True:
        if int(state.get("revision_count", 0)) >= int(state.get("max_revisions", 3)):
            state.setdefault("errors", []).append("Max revisions reached; returning last draft.")
            break

        msg = input("You: ").strip()
        if not msg:
            continue

        low = msg.lower()

        if low in {"approve", "a", "ok", "done"}:
            state["approved"] = True
            break
        if low in {"skip", "s"}:
            state["skipped"] = True
            state.setdefault("errors", []).append("Skipped by user.")
            break
        if low in {"help", "?"}:
            print("\nExamples:")
            print("- Make it maximum 150 characters.")
            print("- Remove placeholders and ask for their budget.")
            print("- Make it more formal.")
            print("- Add a demo CTA for Tue/Wed.\n")
            continue

        state["feedback"] = msg
        break

    return state


def node_apply_feedback(state: EmailState) -> EmailState:
    fb = (state.get("feedback") or "").strip()
    if not fb:
        return state

    current = state.get("draft", "")
    sig = state.get("signature", "")

    revision_email = dict(state["email"])
    revision_email["body"] = (
        "You are editing an existing email draft.\n"
        "Return ONLY the revised email text. No commentary.\n\n"
        "=== CURRENT DRAFT ===\n"
        f"{current}\n\n"
        "=== EDIT INSTRUCTIONS (must follow) ===\n"
        f"{fb}\n\n"
        "=== REQUIRED SIGNATURE (must be at end) ===\n"
        f"{sig}\n"
    )

    state["draft"] = draft_reply(revision_email, {"department": state.get("department_id", "needs_review")})

    # Optional hard constraint: enforce max characters if user asks
    m = re.search(r"max(?:imum)?\s*(\d{2,5})\s*char", fb.lower())
    if m:
        limit = int(m.group(1))
        state["draft"] = (state["draft"] or "").strip()[:limit].rstrip()

    state["revision_count"] = int(state.get("revision_count", 0)) + 1
    state["feedback"] = None
    return state


def route_after_review(state: EmailState) -> Literal["apply_feedback", "end"]:
    if state.get("approved") or state.get("skipped"):
        return "end"
    if (state.get("feedback") or "").strip():
        return "apply_feedback"
    return "end"


def build_graph():
    g = StateGraph(EmailState)

    g.add_node("load_config", node_load_config)
    g.add_node("route_assign", node_route_and_assign)
    g.add_node("draft", node_draft)
    g.add_node("chat_review", node_chat_review)
    g.add_node("apply_feedback", node_apply_feedback)

    g.set_entry_point("load_config")
    g.add_edge("load_config", "route_assign")
    g.add_edge("route_assign", "draft")
    g.add_edge("draft", "chat_review")

    g.add_conditional_edges("chat_review", route_after_review, {"apply_feedback": "apply_feedback", "end": END})
    g.add_edge("apply_feedback", "draft")

    return g.compile()
