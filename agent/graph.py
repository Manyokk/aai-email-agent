from __future__ import annotations

import re
from typing import Dict, Any, Literal

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
# Helpers: routing + assignment
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
    dept_ids = [d.strip() for d in dept_ids if d and d.strip()]
    if not dept_ids:
        return {"department_id": "needs_review", "confidence": 0.40}

    allowed = dept_ids + ["needs_review"]

    subject = str(email.get("subject") or "")
    body = str(email.get("body") or email.get("text") or "")
    sender = str(email.get("from") or email.get("sender") or "")
    to_line = str(_get_to_addresses(email) or "")

    blob = f"FROM: {sender}\nTO: {to_line}\nSUBJECT: {subject}\nBODY:\n{body}"

    system = (
        "You are an email routing classifier for ONE company.\n"
        "Choose the best department_id from the ALLOWED LIST.\n"
        "Return ONLY the department_id. No extra words.\n\n"
        f"ALLOWED LIST: {allowed}\n"
    )

    try:
        llm = ChatOllama(
            model="llama3.2",
            temperature=0.0,
            base_url="http://localhost:11434",
        )
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=blob)])
        raw = (resp.content or "").strip().strip('"').strip("'").lower()

        allowed_lower = {a.lower() for a in allowed}
        if raw in allowed_lower:
            conf = 0.65 if raw != "needs_review" else 0.45
            return {"department_id": raw, "confidence": conf}

        return {"department_id": "needs_review", "confidence": 0.45}

    except Exception:
        return {"department_id": "needs_review", "confidence": 0.40}


def route_department(cfg: Dict[str, Any], email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Priority:
    1) Alias routing
    2) Keyword routing
    3) LLM fallback routing
    4) needs_review
    """
    dept_map = alias_to_department(cfg)
    dept_names = dept_id_to_name(cfg)

    # 1) Alias routing
    to_text = _get_to_addresses(email).lower()
    for addr, dep_id in dept_map.items():
        if addr in to_text:
            return {"department_id": dep_id, "confidence": 0.95}

    # 2) Keyword routing
    body = (email.get("body") or email.get("text") or "").lower()
    subject = (email.get("subject") or "").lower()
    blob = subject + "\n" + body

    for rule in (cfg.get("routing_rules", {}) or {}).get("keyword_to_department", []):
        if not isinstance(rule, dict):
            continue
        dep_id = rule.get("department_id")
        kws = rule.get("keywords") or []
        if not dep_id or not isinstance(kws, list):
            continue
        for kw in kws:
            kw_s = str(kw).lower().strip()
            if kw_s and kw_s in blob:
                return {"department_id": str(dep_id), "confidence": 0.75}

    # 3) LLM fallback routing
    if dept_names:
        return llm_route_department(cfg, email)

    # 4) Fallback
    return {"department_id": "needs_review", "confidence": 0.40}


def _signature_for(cfg: Dict[str, Any], email: str) -> str:
    e = (email or "").strip().lower()
    for emp in cfg.get("employees", []) or []:
        if isinstance(emp, dict) and (emp.get("email") or "").strip().lower() == e:
            return str(emp.get("signature") or "").strip()
    return ""


def assign_owner(cfg: Dict[str, Any], dept_id: str, rr_state: Dict[str, int]) -> Dict[str, str]:
    emps_by_dep = employees_by_department(cfg)
    candidates = emps_by_dep.get(dept_id, []) or []

    fb = fallback_employee_email(cfg)

    if not candidates:
        if fb:
            return {"owner_email": fb, "signature": _signature_for(cfg, fb)}
        emps = cfg.get("employees", []) or []
        if emps:
            e0 = emps[0]
            email = (e0.get("email") or "").strip().lower()
            return {"owner_email": email, "signature": _signature_for(cfg, email)}
        return {"owner_email": "", "signature": ""}

    idx = int(rr_state.get(dept_id, 0))
    chosen = candidates[idx % len(candidates)]
    rr_state[dept_id] = (idx + 1) % len(candidates)

    owner = (chosen.get("email") or "").strip().lower()
    sig = str(chosen.get("signature") or "").strip()
    return {"owner_email": owner, "signature": sig}


# ----------------------------
# Nodes
# ----------------------------

def node_load_config(state: EmailState) -> EmailState:
    path = state.get("config_path", "config/company_config.json")
    state["config_path"] = path
    state["config"] = load_company_config(path)

    state.setdefault("errors", [])
    state.setdefault("revision_count", 0)
    state.setdefault("max_revisions", 3)
    state.setdefault("approved", False)
    state.setdefault("skipped", False)

    state.setdefault("_rr_state", {})
    return state


def node_route_and_assign(state: EmailState) -> EmailState:
    cfg = state["config"]
    email = state["email"]

    routed = route_department(cfg, email)
    state["department_id"] = routed["department_id"]
    state["confidence"] = float(routed["confidence"])

    tones = dept_id_to_tone(cfg)
    default_tone = (cfg.get("company", {}) or {}).get("default_tone")
    state["tone"] = tones.get(state["department_id"]) or (str(default_tone).strip() if default_tone else None)

    rr_state = state.get("_rr_state") or {}
    assigned = assign_owner(cfg, state["department_id"], rr_state)
    state["_rr_state"] = rr_state
    state["owner_email"] = assigned.get("owner_email", "")
    state["signature"] = assigned.get("signature", "")

    return state


def node_draft(state: EmailState) -> EmailState:
    cfg = state["config"]
    dept_names = dept_id_to_name(cfg)
    dept_name = dept_names.get(state.get("department_id", ""), state.get("department_id", "needs_review"))

    email = dict(state["email"])
    tone = state.get("tone")
    sig = state.get("signature")

    constraints = []
    if tone:
        constraints.append(f"TONE: {tone}")
    constraints.append(f"DEPARTMENT: {dept_name}")
    if state.get("owner_email"):
        constraints.append(f"RESPONDER: {state['owner_email']}")
    if sig:
        constraints.append("SIGNATURE (use exactly at end):\n" + sig)

    email["body"] = (email.get("body", "") + "\n\n---\n" + "\n\n".join(constraints) + "\n")

    triage_result = {"department": dept_name, "confidence": state.get("confidence", 0.0)}
    state["draft"] = draft_reply(email, triage_result)
    return state


def node_chat_review(state: EmailState) -> EmailState:
    email = state["email"]
    cfg = state["config"]
    dept_names = dept_id_to_name(cfg)
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

    print("Commands: approve/a | skip/s | help")
    print("Anything else = edit instruction and we revise.\n")

    while True:
        if int(state.get("revision_count", 0)) >= int(state.get("max_revisions", 3)):
            state.setdefault("errors", []).append("Max revisions reached; returning last draft.")
            break

        msg = input("You: ").strip()
        if not msg:
            continue

        low = msg.lower()

        if low in {"a", "approve", "ok", "done"}:
            state["approved"] = True
            break
        if low in {"s", "skip"}:
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

    triage_result = {"department": state.get("department_id", "needs_review"), "confidence": state.get("confidence", 0.0)}
    state["draft"] = draft_reply(revision_email, triage_result)

    # hard constraint: if user says "max 150 characters" enforce it
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
