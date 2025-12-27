from __future__ import annotations

import re
from typing import Any


_SIGNATURE_SPLIT_PATTERNS = [
    r"\n--\s*\n",          # common signature delimiter
    r"\nRegards,\n",
    r"\nBest regards,\n",
    r"\nSincerely,\n",
]

_QUOTED_REPLY_PATTERNS = [
    r"\nOn .* wrote:\n",   # quoted reply header
    r"\nFrom: .*",         # forwarded/reply blocks
]


def preprocess_email(email: dict[str, Any]) -> dict[str, str]:
    """
    Normalize and clean an email dict to a stable schema:
    {id, from, subject, body}

    - Guarantees keys exist as strings (empty if missing)
    - Normalizes line breaks
    - Strips leading/trailing whitespace
    - Light cleanup of signatures and quoted replies (basic)
    """
    eid = str(email.get("id") or "").strip()
    sender = str(email.get("from") or "").strip()
    subject = str(email.get("subject") or "").strip()
    body = str(email.get("body") or "")

    # Normalize newlines
    body = body.replace("\r\n", "\n").replace("\r", "\n").strip()

    # Remove obvious quoted reply sections (basic heuristic)
    for pat in _QUOTED_REPLY_PATTERNS:
        m = re.search(pat, body, flags=re.IGNORECASE)
        if m:
            body = body[: m.start()].strip()
            break

    # Remove common signature blocks (basic heuristic)
    for pat in _SIGNATURE_SPLIT_PATTERNS:
        parts = re.split(pat, body, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) > 1:
            body = parts[0].strip()
            break

    # Guarantee schema
    return {
        "id": eid,
        "from": sender,
        "subject": subject,
        "body": body,
    }
