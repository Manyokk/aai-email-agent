"""Tests for router."""
import json
import tempfile
import shutil
from pathlib import Path
from routing.router import route


def test_route_creates_file():
    """Test route creates JSON file with correct structure."""
    temp_dir = tempfile.mkdtemp()
    import os
    os.chdir(temp_dir)
    
    try:
        email = {"id": "test-123", "from": "test@example.com", "subject": "Test", "body": "Body"}
        triage = {"department": "Support", "confidence": 0.9, "summary": "Test summary"}
        draft = "Draft reply"
        
        path = route(email, triage, draft)
        
        assert Path(path).exists()
        with open(path) as f:
            data = json.load(f)
        assert data["ticket_id"] == "test-123"
        assert data["department"] == "Support"
        assert data["draft_reply"] == draft
    finally:
        os.chdir("..")
        shutil.rmtree(temp_dir)

