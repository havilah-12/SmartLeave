import json
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
from google.adk.workflow import node
from google.genai import types, Client

ROUTER_MODEL = "gemini-2.5-flash"

class SlotExtractionSchema(BaseModel):
    intent: str = Field(description="One of: 'holiday_only', 'employee_only', 'calculate_only', 'apply_leave'")
    employee_id: Optional[str] = Field(None, description="Employee ID if provided (e.g., EMP001)")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD")
    reason: Optional[str] = Field(None, description="Reason for the leave")

EXTRACTOR_PROMPT = """You are an Intent and Slot Extraction Router for an HR Leave Management System.
Today's Date is: {today}

Analyze the user's message ALONG WITH the existing known state. 
Merge the new information with the existing state and output the completely updated slots.
If the existing state has a value, keep it unless the user explicitly changes it.
If the existing state is "None", try to extract it from the user's message.
Note: Pay attention to relative dates like "tomorrow", "next Monday", etc., and convert them to exact YYYY-MM-DD format using Today's Date.

Possible Intents:
- `holiday_only`: Asking about holidays.
- `employee_only`: Asking about leave balance or profile.
- `calculate_only`: Simulating or calculating leave days.
- `apply_leave`: Applying for a leave.

CURRENT STATE:
Intent: {current_intent}
Employee ID: {current_employee_id}
Start Date: {current_start_date}
End Date: {current_end_date}
Reason: {current_reason}

USER MESSAGE:
{message}
"""

@node(name="intent_slot_extractor")
def intent_slot_extractor(ctx: Any, node_input: Any) -> Any:
    """Extract slots from the user message and merge them into the context state."""
    parts = getattr(ctx.user_content, "parts", None) or []
    user_text = " ".join(getattr(part, "text", "") for part in parts if getattr(part, "text", None)).strip()

    if not user_text:
        ctx.route = "continue"
        return node_input

    client = Client()
    
    current_intent = ctx.state.get("intent", "apply_leave")
    
    prompt = EXTRACTOR_PROMPT.format(
        today=datetime.now().strftime("%Y-%m-%d"),
        current_intent=current_intent,
        current_employee_id=ctx.state.get("leave_request_employee_id", "None"),
        current_start_date=ctx.state.get("leave_request_start_date", "None"),
        current_end_date=ctx.state.get("leave_request_end_date", "None"),
        current_reason=ctx.state.get("leave_request_reason", "None"),
        message=user_text
    )
    
    response = client.models.generate_content(
        model=ROUTER_MODEL, 
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SlotExtractionSchema,
            temperature=0.1
        )
    )
    
    try:
        data = json.loads(response.text)
    except Exception:
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

    ctx.route = "continue"
    return node_input
