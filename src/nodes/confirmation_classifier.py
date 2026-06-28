import json
from typing import Any
from pydantic import BaseModel, Field
from google.adk.workflow import node
from google.genai import types, Client
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import logger, settings

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

@retry(stop=stop_after_attempt(settings.MAX_RETRIES), wait=wait_exponential(multiplier=1, min=settings.RETRY_MIN_WAIT, max=settings.RETRY_MAX_WAIT), reraise=True)
def _classify_confirmation_with_retry(prompt: str) -> str:
    client = Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ConfirmationSchema,
            temperature=0.1
        )
    )
    return response.text

@node(name="confirmation_node")
def confirmation_node(ctx: Any, node_input: Any) -> Any:
    """Use an LLM to evaluate if the user confirmed the leave submission."""
    has_pending = ctx.state.get("pending_submission", False)
    
    parts = getattr(ctx.user_content, "parts", None) or []
    user_text = " ".join(getattr(part, "text", "") for part in parts if getattr(part, "text", None)).strip()

    if not has_pending:
        ctx.route = "continue"
        return user_text
        
    try:
        prompt = PROMPT.format(message=user_text)
        response_text = _classify_confirmation_with_retry(prompt)
        data = json.loads(response_text)
        intent = data.get("intent", "unclear")
    except Exception as e:
        logger.error(f"API Error during confirmation classification: {e}", exc_info=True)
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
