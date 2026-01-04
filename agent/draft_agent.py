# imports
from langchain_google_genai import ChatGoogleGenerativeAI 
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv

def draft_reply(email, triage_result):
    # Load environment variables from .env file in the project root
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    
    #initializing LLM with low randomness (automatically reads GOOGLE_API_KEY from environment)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite", 
        temperature=0.2
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

print(draft_reply("Dear IKEA Team, what is my income?", "Sales"))