import json
from typing import Any
from pydantic import BaseModel, Field
from google.adk.workflow import node
from google.genai import types, Client

class ConfirmationSchema(BaseModel):
    intent: str = Field(description="One of: 'confirmed', 'cancelled', 'unclear'")

PROMPT = """You are an intent classifier determining if a user confirmed a leave request.
The system just asked the user: "Do you want to submit this request? (Yes/No)"

User's response: "{message}"

Classify the intent as:
- 'confirmed': If the user agrees, says yes, sure, go ahead, ok, absolutely, etc.
- 'cancelled': If the user declines, says no, stop, cancel, nope, etc.
- 'unclear': If the user asks a question or says something unrelated.
"""

@node(name="pending_confirmation_router")
def pending_confirmation_router(ctx: Any) -> Any:
    """Use an LLM to evaluate if the user confirmed the leave submission."""
    has_pending = ctx.state.get("pending_submission", False)
    
    parts = getattr(ctx.user_content, "parts", None) or []
    user_text = " ".join(getattr(part, "text", "") for part in parts if getattr(part, "text", None)).strip()

    if not has_pending:
        ctx.route = "continue"
        return user_text
        
    client = Client()
    
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=PROMPT.format(message=user_text),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ConfirmationSchema,
            temperature=0.1
        )
    )
    
    try:
        data = json.loads(response.text)
        intent = data.get("intent", "unclear")
    except Exception:
        intent = "unclear"
        
    if intent == "confirmed":
        ctx.state["confirmation_status"] = "confirmed"
        ctx.route = "confirmed"
        return user_text
    elif intent == "cancelled":
        ctx.state["confirmation_status"] = "cancelled"
        ctx.route = "cancelled"
        return types.Content(role="model", parts=[types.Part(text="Leave application cancelled.")])
    else:
        ctx.state["confirmation_status"] = "unclear"
        ctx.route = "unclear"
        return types.Content(role="model", parts=[types.Part(text="I didn't understand that. Please clearly reply whether you want to submit the request or cancel it.")])
