from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_company_config(path: str) -> Dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))

    # basic sanity defaults
    data.setdefault("company", {})
    data.setdefault("departments", [])
    data.setdefault("inbox_aliases", [])
    data.setdefault("employees", [])
    data.setdefault("assignment", {})
    data.setdefault("routing_rules", {})
    data["routing_rules"].setdefault("keyword_to_department", [])

    return data


def dept_id_to_name(cfg: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for d in cfg.get("departments", []):
        if isinstance(d, dict) and d.get("id") and d.get("name"):
            out[str(d["id"])] = str(d["name"])
    return out


def dept_id_to_tone(cfg: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for d in cfg.get("departments", []):
        if isinstance(d, dict) and d.get("id") and d.get("tone"):
            out[str(d["id"])] = str(d["tone"])
    return out


def alias_to_department(cfg: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for a in cfg.get("inbox_aliases", []):
        if isinstance(a, dict) and a.get("address") and a.get("department_id"):
            out[str(a["address"]).lower().strip()] = str(a["department_id"])
    return out


def employees_by_department(cfg: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for e in cfg.get("employees", []):
        if not isinstance(e, dict):
            continue
        email = (e.get("email") or "").strip().lower()
        if not email:
            continue
        for dep in e.get("department_ids", []) or []:
            dep_id = str(dep)
            out.setdefault(dep_id, []).append(e)
    return out


def fallback_employee_email(cfg: Dict[str, Any]) -> Optional[str]:
    fb = (cfg.get("assignment", {}) or {}).get("fallback_employee_email")
    if isinstance(fb, str) and fb.strip():
        return fb.strip().lower()
    return None
