from __future__ import annotations
from typing import Dict, List


DEPARTMENTS = {"Sales", "Support", "Finance", "NeedsReview"}


def _normalize_text(email: Dict) -> str:
    subject = (email.get("subject") or "").lower()
    body = (email.get("body") or "").lower()
    sender = (email.get("from") or "").lower()
    return f"{subject}\n{body}\n{sender}".strip()


def triage(email: Dict) -> Dict:
    """
    Decide department + confidence + summary + tags.
    """
    text = _normalize_text(email)

    tags: List[str] = []
    department = "NeedsReview"
    confidence = 0.40

    # Sales
    sales_kw = ["pricing", "price", "enterprise", "quote", "demo", "plan", "subscription"]
    if any(k in text for k in sales_kw):
        department = "Sales"
        confidence = 0.80
        tags.append("sales")

    # Support
    support_kw = ["bug", "error", "issue", "login", "log in", "cannot", "can't", "403", "500"]
    if any(k in text for k in support_kw):
        department = "Support"
        confidence = max(confidence, 0.82)
        tags.append("support")

    # Finance
    finance_kw = ["invoice", "payment", "billing", "refund", "charge", "vat", "iban"]
    if any(k in text for k in finance_kw):
        department = "Finance"
        confidence = max(confidence, 0.78)
        tags.append("finance")

    # Ambiguous → NeedsReview
    if len(set(tags)) > 1:
        department = "NeedsReview"
        confidence = 0.55
        tags.append("ambiguous")

    # Empty email
    if not (email.get("subject") or "").strip() and not (email.get("body") or "").strip():
        department = "NeedsReview"
        confidence = 0.20
        tags = ["empty"]

    summary = (email.get("subject") or "").strip()
    if not summary:
        body = (email.get("body") or "")
        summary = body[:80] + ("..." if len(body) > 80 else "")

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
