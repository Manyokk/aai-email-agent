from __future__ import annotations

from typing import Any, Dict


def draft_reply(email: Dict[str, Any], triage_result: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate an INTERNAL draft reply for employees (not customer-facing).

    Input:
      email: {id, from, subject, body}
      triage_result: {department, confidence, summary, tags?}

    Output:
      {"draft_reply": "<text>"}
    """
    dept = str(triage_result.get("department") or "NeedsReview")
    conf = triage_result.get("confidence")
    summary = str(triage_result.get("summary") or "").strip()
    tags = triage_result.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    sender = str(email.get("from") or "").strip()
    subject = str(email.get("subject") or "").strip()
    body = str(email.get("body") or "").strip()

    # Common header for internal note
    header = (
        "INTERNAL DRAFT (TRIAG3)\n"
        "Do NOT send to customer as-is. Use as a starting point.\n\n"
        f"Department: {dept}\n"
        f"Confidence: {conf}\n"
        f"Tags: {', '.join(map(str, tags)) if tags else 'None'}\n"
        f"From: {sender}\n"
        f"Subject: {subject}\n"
    )
    if summary:
        header += f"Summary: {summary}\n"
    header += "\n"

    # Department-specific suggested actions
    if dept.lower() == "sales":
        actions = (
            "Suggested actions:\n"
            "- Confirm the customer's use case and expected user count.\n"
            "- Share pricing tiers and propose a demo call.\n"
            "- Ask about SSO/security requirements if enterprise.\n\n"
        )
    elif dept.lower() == "support":
        actions = (
            "Suggested actions:\n"
            "- Request timestamps, affected users, and error screenshots/logs.\n"
            "- Check service status and recent deployments.\n"
            "- Provide workaround if available; escalate if reproducible.\n\n"
        )
    elif dept.lower() == "finance":
        actions = (
            "Suggested actions:\n"
            "- Locate invoice/order reference and verify payment status.\n"
            "- Confirm billing address/legal entity if changes are requested.\n"
            "- If duplicate charge: validate transactions and initiate refund flow.\n\n"
        )
    else:
        actions = (
            "Suggested actions:\n"
            "- Needs manual review to determine correct owner/team.\n"
            "- Identify missing context; request clarification if needed.\n\n"
        )

    # Include the customer message as context for internal team
    context = (
        "Customer message (context):\n"
        "--------------------------\n"
        f"{body}\n"
    )

    return {"draft_reply": header + actions + context}
