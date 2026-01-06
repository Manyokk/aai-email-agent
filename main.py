from __future__ import annotations

import os
from typing import Any, Dict, List

from ingestion.loader import load_emails
from routing.router import route

from agent.graph import build_graph


def main() -> None:
    data_path = os.getenv("AAI_EMAIL_DATA", "data/sample_emails.json")
    max_revs = int(os.getenv("AAI_MAX_REVISIONS", "2"))

    emails: List[Dict[str, Any]] = load_emails(data_path)
    print(f"[INFO] Loaded {len(emails)} raw emails from {data_path}")

    graph = build_graph()

    for i, email in enumerate(emails, start=1):
        email_id = email.get("id") or email.get("email_id") or f"email_{i:03d}"

        state = {
            "email": email,
            "max_revisions": max_revs,
            "revision_count": 0,
            "feedback": None,
            "errors": [],
            "memory_notes": [],
        }

        try:
            final_state = graph.invoke(state)

            triage_result = {
                "department": final_state.get("department", "NeedsReview"),
                "confidence": float(final_state.get("confidence", 0.0)),
                "summary": final_state.get("summary", ""),
                "tags": final_state.get("tags", []),
            }

            draft_text = final_state.get("draft", "")

            out_path = route(email, triage_result, draft_text)

            print(
                f"[OK] ({i}/{len(emails)}) {email_id} -> "
                f"{triage_result['department']} (conf={triage_result['confidence']:.2f}) -> {out_path}"
            )

            errs = final_state.get("errors") or []
            if errs:
                print(f"[WARN] {email_id}: " + " | ".join(errs))

        except Exception as e:
            print(f"[ERR] ({i}/{len(emails)}) {email_id} failed: {e}")


if __name__ == "__main__":
    main()
