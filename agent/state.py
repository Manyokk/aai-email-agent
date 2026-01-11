from __future__ import annotations

from typing import TypedDict, Optional, List, Dict, Any


class EmailState(TypedDict, total=False):
    email: Dict[str, Any]

    # Company config
    config_path: str
    config: Dict[str, Any]

    # Routing result (company-defined)
    department_id: str
    confidence: float

    # Assignment
    owner_email: str
    signature: str
    tone: Optional[str]

    # Drafting
    draft: str

    # Chat loop
    feedback: Optional[str]
    revision_count: int
    max_revisions: int
    approved: bool
    skipped: bool

    errors: List[str]
