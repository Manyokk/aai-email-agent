import json
from pathlib import Path
from typing import Any


def load_emails(path: str) -> list[dict]:
    """
    Load a list of email objects from a JSON file.

    Expected JSON format:
    [
      {"id": "...", "from": "...", "subject": "...", "body": "..."},
      ...
    ]
    """
    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(f"Email data file not found: {p.resolve()}")

    try:
        data: Any = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {p.resolve()}: {e}") from e

    if not isinstance(data, list):
        raise ValueError("Email data must be a JSON list of email objects")

    # Ensure each item is dict-like
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Email at index {i} is not an object/dict")

    return data
