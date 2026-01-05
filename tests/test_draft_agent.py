"""Tests for draft agent."""
from unittest.mock import patch, MagicMock
from agent.draft_agent import draft_reply


@patch('agent.draft_agent.ChatGoogleGenerativeAI')
@patch('agent.draft_agent.load_dotenv')
def test_draft_reply(mock_load_dotenv, mock_llm_class):
    """Test draft_reply returns LLM response."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "Test reply"
    mock_llm_class.return_value = mock_llm
    
    result = draft_reply("Test email", {"department": "Support"})
    assert result == "Test reply"
    mock_llm.invoke.assert_called_once()

