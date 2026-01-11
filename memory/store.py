from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, List


ALLOWED_DEPARTMENTS = {"Sales", "Support", "Finance", "NeedsReview"}

DEFAULT_MEMORY: Dict[str, Any] = {
    "sender_department": {},
    "sender_owner": {},
    "department_tone": {
        "Sales": "friendly, concise, confident",
        "Support": "empathetic, helpful, step-by-step",
        "Finance": "formal, precise, compliance-focused",
        "NeedsReview": "neutral, ask clarifying questions",
    },
    "department_owners": {
        "Sales": ["sales1@triag3.com"],
        "Support": ["support1@triag3.com"],
        "Finance": ["finance1@triag3.com"],
        "NeedsReview": ["ops@triag3.com"],
    },
    "rr_index": {d: 0 for d in ALLOWED_DEPARTMENTS},
    "employees": {
        "sales1@triag3.com": {"name": "Sales Agent", "title": "Sales", "signature": "Sales Agent\nSales – TRIAG3"},
        "support1@triag3.com": {"name": "Support Agent", "title": "Support", "signature": "Support Agent\nSupport – TRIAG3"},
        "finance1@triag3.com": {"name": "Finance Agent", "title": "Finance", "signature": "Finance Agent\nFinance – TRIAG3"},
        "ops@triag3.com": {"name": "Operations", "title": "Ops", "signature": "Operations\nTRIAG3"},
    },
}


def _safe_key(s: str) -> str:
    return (s or "").strip().lower()


def load_memory(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        save_memory(path, DEFAULT_MEMORY.copy())
        return DEFAULT_MEMORY.copy()

    try:
        data = json.loads(p.read_text(encoding="utf-8"))

        for k, v in DEFAULT_MEMORY.items():
            if k not in data:
                data[k] = v

        # defensive types
        if not isinstance(data.get("sender_department"), dict):
            data["sender_department"] = {}
        if not isinstance(data.get("sender_owner"), dict):
            data["sender_owner"] = {}
        if not isinstance(data.get("department_tone"), dict):
            data["department_tone"] = DEFAULT_MEMORY["department_tone"].copy()
        if not isinstance(data.get("department_owners"), dict):
            data["department_owners"] = DEFAULT_MEMORY["department_owners"].copy()
        if not isinstance(data.get("rr_index"), dict):
            data["rr_index"] = {d: 0 for d in ALLOWED_DEPARTMENTS}
        if not isinstance(data.get("employees"), dict):
            data["employees"] = DEFAULT_MEMORY["employees"].copy()

        # ensure rr keys exist
        for d in ALLOWED_DEPARTMENTS:
            data["rr_index"].setdefault(d, 0)
            data["department_owners"].setdefault(d, DEFAULT_MEMORY["department_owners"].get(d, []))

        return data
    except Exception:
        save_memory(path, DEFAULT_MEMORY.copy())
        return DEFAULT_MEMORY.copy()


def save_memory(path: str, memory: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


# ----------------------------
# Sender -> Department memory
# ----------------------------

def get_sender_department(memory: Dict[str, Any], sender: str) -> Optional[str]:
    key = _safe_key(sender)
    dept = (memory.get("sender_department") or {}).get(key)
    if dept in ALLOWED_DEPARTMENTS:
        return dept
    return None


def set_sender_department(memory: Dict[str, Any], sender: str, department: str) -> None:
    key = _safe_key(sender)
    dept = (department or "").strip()
    if not key or dept not in ALLOWED_DEPARTMENTS:
        return
    memory.setdefault("sender_department", {})
    memory["sender_department"][key] = dept


# ----------------------------
# Sender -> Owner memory
# ----------------------------

def get_sender_owner(memory: Dict[str, Any], sender: str) -> Optional[str]:
    key = _safe_key(sender)
    owner = (memory.get("sender_owner") or {}).get(key)
    if isinstance(owner, str) and owner.strip():
        return owner.strip().lower()
    return None


def set_sender_owner(memory: Dict[str, Any], sender: str, owner_email: str) -> None:
    key = _safe_key(sender)
    owner = _safe_key(owner_email)
    if not key or not owner:
        return
    memory.setdefault("sender_owner", {})
    memory["sender_owner"][key] = owner


# ----------------------------
# Tone by department
# ----------------------------

def get_department_tone(memory: Dict[str, Any], department: str) -> Optional[str]:
    tone = (memory.get("department_tone") or {}).get(department)
    if isinstance(tone, str) and tone.strip():
        return tone.strip()
    return None


# ----------------------------
# Owners + signatures
# ----------------------------

def get_department_owners(memory: Dict[str, Any], department: str) -> List[str]:
    owners = (memory.get("department_owners") or {}).get(department, [])
    if not isinstance(owners, list):
        return []
    return [_safe_key(x) for x in owners if isinstance(x, str) and x.strip()]


def choose_owner_round_robin(memory: Dict[str, Any], department: str) -> Optional[str]:
    owners = get_department_owners(memory, department)
    if not owners:
        return None

    rr = memory.setdefault("rr_index", {})
    idx = int(rr.get(department, 0)) if str(rr.get(department, "0")).isdigit() else 0
    owner = owners[idx % len(owners)]
    rr[department] = (idx + 1) % len(owners)
    return owner


def employee_signature(memory: Dict[str, Any], owner_email: str) -> Optional[str]:
    owner = _safe_key(owner_email)
    emp = (memory.get("employees") or {}).get(owner)
    if isinstance(emp, dict):
        sig = emp.get("signature")
        if isinstance(sig, str) and sig.strip():
            return sig.strip()
    return None


def employee_exists(memory: Dict[str, Any], owner_email: str) -> bool:
    owner = _safe_key(owner_email)
    return owner in (memory.get("employees") or {})
