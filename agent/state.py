from __future__ import annotations

from typing import TypedDict, Optional, List, Dict, Any


class EmailState(TypedDict, total=False):
    # Input
    email: Dict[str, Any]

    # Triage
    department: str
    confidence: float
    summary: str
    tags: List[str]

    # Drafting
    draft: str

    # Human-in-the-loop
    feedback: Optional[str]
    revision_count: int
    max_revisions: int

    # Control / logging
    errors: List[str]

    # Memory hooks (simple placeholder for now)
    memory_notes: List[str]
