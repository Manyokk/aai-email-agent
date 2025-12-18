from __future__ import annotations

import sys
from pathlib import Path

from ingestion.loader import load_emails
from ingestion.preprocess import preprocess_email
from agent.triage_agent import triage
from agent.draft_agent import draft_reply
from routing.router import route


def _ensure_project_root() -> None:
    """
    Make sure script is run from the project root (where main.py sits),
    so relative paths like data/sample_emails.json work.
    """
    root = Path(__file__).resolve().parent
    try:
        import os
        os.chdir(root)
    except Exception:
        pass


def main() -> int:
    _ensure_project_root()

    data_path = "data/sample_emails.json"

    try:
        raw_emails = load_emails(data_path)
    except Exception as e:
        print(f"[FATAL] Failed to load emails from '{data_path}': {e}")
        return 1

    if not isinstance(raw_emails, list) or len(raw_emails) == 0:
        print("[FATAL] No emails found (sample_emails.json is empty or invalid).")
        return 1

    ok, failed = 0, 0
    print(f"[INFO] Loaded {len(raw_emails)} raw emails from {data_path}")

    for idx, raw in enumerate(raw_emails, start=1):
        try:
            email = preprocess_email(raw)

            triage_result = triage(email)
            draft_result = draft_reply(email, triage_result)

            out_file = route(email, triage_result, draft_result)

            dept = triage_result.get("department", "Unknown")
            conf = triage_result.get("confidence", None)
            conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else "n/a"

            print(f"[OK] ({idx}/{len(raw_emails)}) {email.get('id')} -> {dept} (conf={conf_str}) -> {out_file}")
            ok += 1

        except Exception as e:
            failed += 1
            eid = None
            try:
                eid = raw.get("id")
            except Exception:
                pass
            print(f"[FAIL] ({idx}/{len(raw_emails)}) id={eid} error={e}")

    print(f"[DONE] success={ok} failed={failed}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
