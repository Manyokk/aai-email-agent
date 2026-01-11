from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


ALLOWED_DEPARTMENTS = {"Sales", "Support", "Finance", "NeedsReview"}

DEFAULT_MEMORY: Dict[str, Any] = {
    "sender_department": {},
    "department_tone": {
        "Sales": "friendly, concise, confident",
        "Support": "empathetic, helpful, step-by-step",
        "Finance": "formal, precise, compliance-focused",
        "NeedsReview": "neutral, ask clarifying questions",
    },
}


def _safe_sender_key(sender: str) -> str:
    return (sender or "").strip().lower()


def load_memory(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        save_memory(path, DEFAULT_MEMORY.copy())
        return DEFAULT_MEMORY.copy()

    try:
        data = json.loads(p.read_text(encoding="utf-8"))

        # ensure required keys exist
        for k, v in DEFAULT_MEMORY.items():
            if k not in data:
                data[k] = v

        # ensure sender_department is a dict
        if not isinstance(data.get("sender_department"), dict):
            data["sender_department"] = {}

        # ensure department_tone is a dict
        if not isinstance(data.get("department_tone"), dict):
            data["department_tone"] = DEFAULT_MEMORY["department_tone"].copy()

        return data
    except Exception:
        # if memory file is corrupted, reset
        save_memory(path, DEFAULT_MEMORY.copy())
        return DEFAULT_MEMORY.copy()


def save_memory(path: str, memory: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def get_sender_department(memory: Dict[str, Any], sender: str) -> Optional[str]:
    key = _safe_sender_key(sender)
    dept = (memory.get("sender_department") or {}).get(key)
    if dept in ALLOWED_DEPARTMENTS:
        return dept
    return None


def set_sender_department(memory: Dict[str, Any], sender: str, department: str) -> None:
    key = _safe_sender_key(sender)
    dept = (department or "").strip()

    if not key:
        return
    if dept not in ALLOWED_DEPARTMENTS:
        return

    memory.setdefault("sender_department", {})
    memory["sender_department"][key] = dept


def get_department_tone(memory: Dict[str, Any], department: str) -> Optional[str]:
    tone = (memory.get("department_tone") or {}).get(department)
    if isinstance(tone, str) and tone.strip():
        return tone.strip()
    return None


def set_department_tone(memory: Dict[str, Any], department: str, tone: str) -> None:
    dept = (department or "").strip()
    t = (tone or "").strip()

    if not dept or dept not in ALLOWED_DEPARTMENTS:
        return
    if not t:
        return

    memory.setdefault("department_tone", {})
    memory["department_tone"][dept] = t
