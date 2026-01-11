from __future__ import annotations

from typing import TypedDict, Optional, List, Dict, Any


class EmailState(TypedDict, total=False):
    # Input
    email: Dict[str, Any]

    # Memory (persistent)
    memory_path: str
    memory: Dict[str, Any]
    used_sender_override: bool

    # Triage
    department: str
    confidence: float
    summary: str
    tags: List[str]

    # Drafting
    draft: str
    tone: Optional[str]

    # Human-in-the-loop
    feedback: Optional[str]
    revision_count: int
    max_revisions: int

    # Control / logging
    errors: List[str]
