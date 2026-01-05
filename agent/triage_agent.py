from __future__ import annotations

from typing import Dict, List, Tuple


DEPARTMENTS = ("Sales", "Support", "Finance", "NeedsReview")


def _normalize_text(email: Dict) -> str:
    subject = (email.get("subject") or "").lower()
    body = (email.get("body") or "").lower()
    sender = (email.get("from") or "").lower()
    return f"{subject}\n{body}\n{sender}".strip()


def _count_hits(text: str, keywords: List[str]) -> int:
    return sum(1 for k in keywords if k in text)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def triage(email: Dict) -> Dict:
    """
    Decide department + confidence + summary + tags.

    Output contract:
    {
      "department": "Sales" | "Support" | "Finance" | "NeedsReview",
      "confidence": float (0..1),
      "summary": str,
      "tags": list[str]
    }
    """
    text = _normalize_text(email)

    subject_raw = (email.get("subject") or "").strip()
    body_raw = (email.get("body") or "").strip()
    if not subject_raw and not body_raw:
        return {
            "department": "NeedsReview",
            "confidence": 0.20,
            "summary": "",
            "tags": ["empty"],
        }

    sales_kw = [
        "pricing", "price", "enterprise", "quote", "demo", "subscription", "plan", "upgrade",
        "rfp", "proposal", "procurement", "sla", "security documentation", "security", "compliance",
        "discount", "student", "non-profit", "nonprofit",
        "sso", "saml", "scim", "identity provider", "okta", "azure ad",
        "trial", "pilot", "evaluation", "onboarding timeline",
        "partnership", "co-marketing", "comarketing",
    ]

    support_kw = [
        "bug", "error", "issue", "problem", "cannot", "can't", "cant", "failed", "failure",
        "login", "log in", "password", "reset password", "password reset", "403", "401", "500",
        "suspicious", "compromise", "unknown ip", "lock the account", "audit",
        "slow", "latency", "timeout", "performance", "dashboard", "down", "outage",
        "webhook", "events", "event", "firing", "stopped",
        "complaint", "escalated", "escalation", "forwarding",
        "csv", "export",
    ]

    finance_kw = [
        "invoice", "inv-", "billing", "payment", "refund", "charge", "charged", "receipt",
        "vat", "iban", "bank",
        "billing address", "accounts payable", "ap@", "w-9", "w9", "tax", "vendor setup",
    ]

    s_hits = _count_hits(text, sales_kw)
    sup_hits = _count_hits(text, support_kw)
    f_hits = _count_hits(text, finance_kw)

    tags: List[str] = []
    if s_hits:
        tags.append("sales")
    if sup_hits:
        tags.append("support")
    if f_hits:
        tags.append("finance")

    # If nothing matched, it's genuinely unclear
    if s_hits == 0 and sup_hits == 0 and f_hits == 0:
        # Some extra lightweight heuristics for common unknowns:
        # HR/reference checks should go to NeedsReview (not Sales/Support/Finance).
        if "reference check" in text or "employment dates" in text or "hr" in text:
            return {
                "department": "NeedsReview",
                "confidence": 0.35,
                "summary": subject_raw or (body_raw[:80] + ("..." if len(body_raw) > 80 else "")),
                "tags": ["hr"],
            }

        return {
            "department": "NeedsReview",
            "confidence": 0.40,
            "summary": subject_raw or (body_raw[:80] + ("..." if len(body_raw) > 80 else "")),
            "tags": ["unclear"],
        }

    # --- Tie-break rule (IMPORTANT): Support > Finance > Sales ---
    # We choose the department with highest hits, but prioritize Support for safety.
    # This prevents "enterprise + support" from being thrown into NeedsReview.
    department: str
    if sup_hits >= max(f_hits, s_hits) and sup_hits > 0:
        department = "Support"
    elif f_hits >= s_hits and f_hits > 0:
        department = "Finance"
    else:
        department = "Sales"

    # Confidence: base per dept + bump per hit (capped)
    base = {"Sales": 0.70, "Support": 0.72, "Finance": 0.70}[department]
    hits = {"Sales": s_hits, "Support": sup_hits, "Finance": f_hits}[department]
    confidence = _clamp(base + 0.06 * min(hits, 3), 0.0, 0.92)

    matched_groups = sum(1 for x in (s_hits, sup_hits, f_hits) if x > 0)
    if matched_groups >= 2:
        tags.append("ambiguous")
        confidence = min(confidence, 0.75) 

    
    summary = subject_raw or (body_raw[:80] + ("..." if len(body_raw) > 80 else ""))


    if department not in DEPARTMENTS:
        department = "NeedsReview"
        confidence = 0.30
        tags.append("fallback")

    return {
        "department": department,
        "confidence": float(confidence),
        "summary": summary,
        "tags": sorted(set(tags)),
    }
