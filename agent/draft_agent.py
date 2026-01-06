# imports
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

def draft_reply(email, triage_result):
    # Initialize Ollama LLM (connects to local Ollama instance)
    # Default model is "llama3.2" - change if you have a different model
    llm = ChatOllama(
        model="llama3.2",  # Change to your preferred Ollama model (e.g., "llama2", "mistral", "phi3")
        temperature=0.2,
        base_url="http://localhost:11434"  # Default Ollama API endpoint
    )
    
    # Extract department from triage_result structure:
    # {
    #   "department": "Sales" | "Support" | "Finance" | "NeedsReview",
    #   "confidence": float,
    #   "summary": str,
    #   "tags": list[str]
    # }
    if isinstance(triage_result, dict):
        department = triage_result.get("department", "Unknown")
    else:
        # Fallback for plain text (backward compatibility)
        department = str(triage_result)
    
    # email is plain text (email content as string)
    email_content = str(email)
    
    # Create prompt with proper string formatting
    draft_prompt = f"Our Company name is TRIAG3. Create an answer to the email from the customer. Use the following Department this email is directed to: {department}"
    
    messages = [
        SystemMessage(content=draft_prompt),
        HumanMessage(content=email_content)
    ]
    
    #llm call
    response = llm.invoke(messages)
    # Return plain text content from the response
    return response.content

#newcode
