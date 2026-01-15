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
        # Strip // comments before parsing (allows commented-out emails to remain in file)
        content = p.read_text(encoding="utf-8")
        
        # Find the last closing bracket to determine where JSON ends
        last_bracket_pos = content.rfind(']')
        if last_bracket_pos == -1:
            raise ValueError("No closing bracket found in JSON file")
        
        # Only process content up to and including the closing bracket
        json_content = content[:last_bracket_pos + 1]
        
        # Strip // comments from the JSON content
        lines = []
        for line in json_content.split('\n'):
            # Remove // comments but preserve the line structure
            if '//' in line:
                comment_pos = line.find('//')
                # Check if // is inside a string (basic check)
                before_comment = line[:comment_pos]
                if before_comment.count('"') % 2 == 0:  # Even number of quotes = // is not in string
                    line = before_comment.rstrip()
            lines.append(line.rstrip())
        
        cleaned_content = '\n'.join(lines)
        data: Any = json.loads(cleaned_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {p.resolve()}: {e}") from e

    if not isinstance(data, list):
        raise ValueError("Email data must be a JSON list of email objects")

    # Ensure each item is dict-like
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Email at index {i} is not an object/dict")

    return data
