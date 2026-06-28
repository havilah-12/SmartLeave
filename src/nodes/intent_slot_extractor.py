import json
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
from google.adk.workflow import node
from google.genai import types, Client
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import logger, settings

ROUTER_MODEL = "gemini-2.5-flash"

class SlotExtractionSchema(BaseModel):
    intent: str = Field(description="One of: 'holiday_only', 'employee_only', 'calculate_only', 'apply_leave', 'revoke_leave', 'unknown'")
    employee_id: Optional[str] = Field(None, description="Employee ID if provided (e.g., EMP001)")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD")
    reason: Optional[str] = Field(None, description="Reason for the leave")
    leave_type_preference: Optional[str] = Field(None, description="Whether the user wants to use 'paid', 'unpaid', or 'medical' leave")

EXTRACTOR_PROMPT = """You are an Intent and Slot Extraction Router for an HR Leave Management System.
Today's Date is: {today}

Analyze the user's message ALONG WITH the existing known state. 
Merge the new information with the existing state and output the completely updated slots.
If the existing state has a value, keep it unless the user explicitly changes it.
If the existing state is "None", try to extract it from the user's message.
Note: Pay attention to relative dates like "tomorrow", "next Monday", etc., and convert them to exact YYYY-MM-DD format using Today's Date.

Possible Intents:
- "apply_leave": User wants to apply for a new leave/vacation/sick day.
- "revoke_leave": User wants to cancel or revoke an already-approved leave.
- "employee_only": User just wants to check their own profile, balance, or details.
- "holiday_only": User just wants to check the company holiday calendar.
- "calculate_only": User just wants to calculate working days without submitting.
- "unknown": Unrelated chatting.

CURRENT STATE:
Intent: {current_intent}
Employee ID: {current_employee_id}
Start Date: {current_start_date}
End Date: {current_end_date}
Reason: {current_reason}
Leave Type Preference: {current_leave_type}

USER MESSAGE:
{message}
"""

@retry(stop=stop_after_attempt(settings.MAX_RETRIES), wait=wait_exponential(multiplier=1, min=settings.RETRY_MIN_WAIT, max=settings.RETRY_MAX_WAIT), reraise=True)
def _extract_slots_with_retry(prompt: str) -> str:
    client = Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=ROUTER_MODEL, 
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SlotExtractionSchema,
            temperature=0.1
        )
    )
    return response.text

@node(name="parse_request_node")
def parse_request_node(ctx: Any, node_input: Any) -> Any:
    """Extract slots from the user message and merge them into the context state."""
    parts = getattr(ctx.user_content, "parts", None) or []
    user_text = " ".join(getattr(part, "text", "") for part in parts if getattr(part, "text", None)).strip()

    if not user_text:
        ctx.route = "continue"
        return node_input

    current_intent = ctx.state.get("intent", "None")
    
    prompt = EXTRACTOR_PROMPT.format(
        today=datetime.now().strftime("%Y-%m-%d"),
        current_intent=current_intent,
        current_employee_id=ctx.state.get("leave_request_employee_id", "None"),
        current_start_date=ctx.state.get("leave_request_start_date", "None"),
        current_end_date=ctx.state.get("leave_request_end_date", "None"),
        current_reason=ctx.state.get("leave_request_reason", "None"),
        current_leave_type=ctx.state.get("leave_type_preference", "None"),
        message=user_text
    )
    
    try:
        response_text = _extract_slots_with_retry(prompt)
        data = json.loads(response_text)
    except Exception as e:
        logger.error(f"API Error during intent extraction: {e}", exc_info=True)
        data = {"intent": "apply_leave"}
        
    ctx.state["intent"] = data.get("intent", "apply_leave")
    
    if data.get("employee_id") and data.get("employee_id") != "None":
        ctx.state["leave_request_employee_id"] = data["employee_id"]
    if data.get("start_date") and data.get("start_date") != "None":
        ctx.state["leave_request_start_date"] = data["start_date"]
    if data.get("end_date") and data.get("end_date") != "None":
        ctx.state["leave_request_end_date"] = data["end_date"]
    if data.get("reason") and data.get("reason") != "None":
        ctx.state["leave_request_reason"] = data["reason"]
    if data.get("leave_type_preference") and data.get("leave_type_preference") != "None":
        ctx.state["leave_type_preference"] = data["leave_type_preference"]

    ctx.route = "continue"
    return node_input
