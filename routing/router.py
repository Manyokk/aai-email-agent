from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_department(name: Any) -> str:
    dept = str(name or "NeedsReview").strip()
    # avoid weird folder names
    dept = dept.replace("/", "_").replace("\\", "_")
    return dept if dept else "NeedsReview"


def route(email: Dict[str, Any], triage_result: Dict[str, Any], draft_result: Dict[str, Any]) -> str:
    """
    Create a ticket JSON file and save it into outputs/<department>/.

    Returns:
      str path to created ticket file
    """
    dept = _safe_department(triage_result.get("department"))
    out_dir = Path("outputs") / dept
    out_dir.mkdir(parents=True, exist_ok=True)

    email_id = str(email.get("id") or "unknown").strip() or "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    ticket_id = f"{email_id}_{ts}"

    ticket = {
        "ticket_id": ticket_id,
        "created_at": _utc_now_iso(),
        "department": dept,
        "confidence": triage_result.get("confidence"),
        "from": email.get("from"),
        "subject": email.get("subject"),
        "summary": triage_result.get("summary"),
        "tags": triage_result.get("tags", []),
        "draft_reply": draft_result.get("draft_reply"),
        "raw_body": email.get("body"),
    }

    out_path = out_dir / f"{ticket_id}.json"
    out_path.write_text(json.dumps(ticket, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out_path)
