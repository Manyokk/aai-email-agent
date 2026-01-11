from __future__ import annotations

import os
from collections import Counter
from typing import Any, Dict, List

from ingestion.loader import load_emails
from routing.router import route

from agent.graph import build_graph
from config.loader import load_company_config, dept_id_to_name


def print_department_summary(counts: Counter, dept_id_to_name_map: Dict[str, str]) -> None:
    if not counts:
        print("\n[SUMMARY] No emails processed.\n")
        return

    total = sum(counts.values())
    max_label_len = max(len(dept_id_to_name_map.get(k, k)) for k in counts.keys())
    max_count = max(counts.values())

    print("\n" + "=" * 60)
    print("[SUMMARY] Emails per department")
    print("=" * 60)

    for dept_id, c in counts.most_common():
        label = dept_id_to_name_map.get(dept_id, dept_id)
        pct = (c / total) * 100 if total else 0.0
        bar_len = int((c / max_count) * 30) if max_count else 0
        bar = "█" * bar_len
        print(f"{label:<{max_label_len}}  {c:>4}  ({pct:>5.1f}%)  {bar}")

    print("-" * 60)
    print(f"{'TOTAL':<{max_label_len}}  {total:>4}")
    print("=" * 60 + "\n")


def main() -> None:
    data_path = os.getenv("AAI_EMAIL_DATA", "data/sample_emails.json")
    config_path = os.getenv("AAI_COMPANY_CONFIG", "config/company_config.json")
    max_revs = int(os.getenv("AAI_MAX_REVISIONS", "3"))

    emails: List[Dict[str, Any]] = load_emails(data_path)
    print(f"[INFO] Loaded {len(emails)} raw emails from {data_path}")
    print(f"[INFO] Using company config from {config_path}")

    cfg = load_company_config(config_path)
    dept_map = dept_id_to_name(cfg)

    graph = build_graph()

    dept_counts: Counter = Counter()

    for i, email in enumerate(emails, start=1):
        email_id = email.get("id") or email.get("email_id") or f"email_{i:03d}"

        state = {
            "email": email,
            "config_path": config_path,
            "max_revisions": max_revs,
            "revision_count": 0,
            "feedback": None,
            "errors": [],
            "approved": False,
            "skipped": False,
        }

        try:
            final_state = graph.invoke(state)

            dept_id = (final_state.get("department_id") or "needs_review").strip().lower()
            if not dept_id:
                dept_id = "needs_review"

            dept_counts[dept_id] += 1

            dept_label = dept_map.get(dept_id, dept_id)

            triage_result = {
                # IMPORTANT: use dept_id directly so router creates outputs/<dept_id>/
                "department": dept_id,
                "confidence": float(final_state.get("confidence", 0.0)),
                "summary": final_state.get("summary", ""),
                "tags": final_state.get("tags", []),
            }

            draft_text = final_state.get("draft", "")
            out_path = route(email, triage_result, draft_text)

            print(
                f"[OK] ({i}/{len(emails)}) {email_id} -> "
                f"{dept_label} (conf={triage_result['confidence']:.2f}) -> {out_path}"
            )

            errs = final_state.get("errors") or []
            if errs:
                print(f"[WARN] {email_id}: " + " | ".join(errs))

        except Exception as e:
            print(f"[ERR] ({i}/{len(emails)}) {email_id} failed: {e}")

    print_department_summary(dept_counts, dept_map)


if __name__ == "__main__":
    main()
