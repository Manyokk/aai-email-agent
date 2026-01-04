import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def route(email: Dict[str, Any], triage_result: Dict[str, Any], draft_result: str) -> str:
    """
    Route email to appropriate department folder and create ticket JSON file.
    
    Args:
        email: Preprocessed email dictionary containing email data
        triage_result: Dictionary with structure:
            {
                "department": "Sales" | "Support" | "Finance" | "NeedsReview",
                "confidence": float,
                "summary": str,
                "tags": list[str]
            }
        draft_result: Plain text draft reply from draft_agent
        
    Returns:
        str: Path to the created JSON file
    """
    # Extract fields from triage_result
    department = triage_result.get("department", "Unknown")
    confidence = triage_result.get("confidence", None)
    triage_summary = triage_result.get("summary", "")
    tags = triage_result.get("tags", [])
    
    # Extract ticket_id from email
    ticket_id = email.get("id", email.get("ticket_id", "unknown"))
    
    # Create outputs directory structure
    outputs_dir = Path("outputs")
    department_dir = outputs_dir / department
    department_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare ticket data
    # Use triage summary if available, otherwise fall back to email summary or first 200 chars of body
    summary = triage_summary or email.get("summary", email.get("body", "")[:200])
    
    ticket_data = {
        "ticket_id": str(ticket_id),
        "department": department,
        "confidence": confidence,
        "from": email.get("from", email.get("sender", "")),
        "subject": email.get("subject", ""),
        "summary": summary,
        "draft_reply": draft_result,
        "raw_body": email.get("body", email.get("content", email.get("text", ""))),
        "timestamp": datetime.now().isoformat()
    }
    
    # Create JSON file path
    json_file_path = department_dir / f"{ticket_id}.json"
    
    # Write JSON file
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(ticket_data, f, indent=2, ensure_ascii=False)
    
    # Return the file path as string
    return str(json_file_path)

