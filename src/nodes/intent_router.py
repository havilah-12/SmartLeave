import json
from typing import Any
from pydantic import BaseModel, Field
from google.adk.workflow import node
from google.genai import types, Client

from config.settings import settings, logger

class RouterDecision(BaseModel):
    next_action: str = Field(description="One of: 'run_pipeline', 'ready_for_calculation', 'submit_leave', 'hr_action', 'end'")
    missing_info_message: str = Field(description="If 'end', the message to display to the user.")
    extracted_employee_id: str = Field(description="Employee ID if found in history")
    extracted_start_date: str = Field(description="Start Date (YYYY-MM-DD) if found")
    extracted_end_date: str = Field(description="End Date (YYYY-MM-DD) if found")
    extracted_reason: str = Field(description="Reason for leave if found")
    extracted_leave_type: str = Field(description="paid, unpaid, or medical. Empty if not yet provided.")
    hr_action_type: str = Field(description="If next_action is 'hr_action', one of: 'approve', 'reject'. Empty otherwise.")
    hr_target_employee_id: str = Field(description="If next_action is 'hr_action', the employee ID they are taking action on.")

@node(name="intent_router_node")
def intent_router_node(ctx: Any, node_input: Any) -> Any:
    """Central Brain Node that dynamically routes execution based on state."""
    user_msg = ""
    if hasattr(node_input, "parts"):
        user_msg = " ".join([p.text for p in node_input.parts if p.text])
    
    # Manually extract only the keys the router needs to avoid ADK State attribute errors
    state = {
        "leave_request_employee_id": ctx.state.get("leave_request_employee_id"),
        "leave_request_start_date": ctx.state.get("leave_request_start_date"),
        "leave_request_end_date": ctx.state.get("leave_request_end_date"),
        "leave_request_reason": ctx.state.get("leave_request_reason"),
        "leave_type_preference": ctx.state.get("leave_type_preference"),
        "employee_lookup_status": ctx.state.get("employee_lookup_status"),
        "has_leave_overlap": ctx.state.get("has_leave_overlap"),
        "confirmation_status": ctx.state.get("confirmation_status")
    }
        
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""You are the Central Orchestrator Router for an HR Leave System.
Analyze the user's message and the current system state, then decide the next action.

USER MESSAGE: "{user_msg}"
CURRENT SYSTEM STATE: {json.dumps(state, default=str)}
TODAY'S DATE: {today_str}

CRITICAL INSTRUCTION ON DATES: You MUST convert any relative dates (e.g., "next Monday", "upcoming Friday", "tomorrow", "next week") or dates missing a year (e.g., "July 1st") into strict `YYYY-MM-DD` format using TODAY'S DATE ({today_str}) as the mathematical reference point. Never output relative words in the extracted date fields!

RULES:
1. If the user states they are HR (e.g. "I am HR001") AND asks to approve or reject/cancel a pending leave for another employee (e.g. "Approve EMP009's leave"): output next_action='hr_action', extract their HR ID into 'extracted_employee_id', set 'hr_action_type' to 'approve' or 'reject', and set 'hr_target_employee_id'.
2. If confirmation_status is 'pending' and the user confirms they want to submit (e.g., 'yes', 'do it'), output next_action='submit_leave'. If they decline (e.g., 'no', 'cancel'), output next_action='end' and say it was cancelled.
3. STRICT RULE: Before you can do anything else, you MUST have Employee ID, Start Date, End Date, AND Reason. If ANY of these 4 are missing (especially Reason), output next_action='end' and ask the user for the missing ones. Do NOT output run_pipeline if Reason is missing!
4. If employee_lookup_status is 'not_found', output next_action='end' and inform the user their Employee ID was invalid and they need to provide a correct one.
5. If ALL 4 required slots (ID, Start, End, Reason) are present and employee_lookup_status is None (meaning we haven't checked the DB yet), output next_action='run_pipeline'.
6. If employee_lookup_status IS 'found', check if there is an overlap (has_leave_overlap). If True, output next_action='end' and tell them to pick new dates.
7. If employee is found, no overlap, but they haven't specified a leave_type preference (paid/unpaid/medical), output next_action='end' to ask them.
8. If everything is found, verified, and preference is set (and confirmation_status is not pending), output next_action='ready_for_calculation'.
9. If the user wants to revoke a leave, output next_action='submit_leave'.
10. If it's just a greeting or unrelated, output next_action='end' and provide a greeting in missing_info_message. It MUST say exactly: 'Hi, I'm your Smart Leave Assistant! I can help you easily apply for leave, check your balances, and cancel existing requests.'

Extract all slots you can find and preserve existing ones.
"""
    client = Client(api_key=settings.GEMINI_API_KEY)
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RouterDecision,
                temperature=0.0
            )
        )
        decision = RouterDecision.model_validate_json(response.text)
    except Exception as e:
        logger.error(f"Router LLM Error: {e}", exc_info=True)
        ctx.route = "end"
        return types.Content(role="model", parts=[types.Part(text="I encountered a routing error. Could you repeat that?")])
        
    # Update State
    dates_changed = False
    
    if decision.extracted_employee_id:
        ctx.state["leave_request_employee_id"] = decision.extracted_employee_id
    if decision.extracted_start_date:
        if decision.extracted_start_date != ctx.state.get("leave_request_start_date"):
            ctx.state["leave_request_start_date"] = decision.extracted_start_date
            dates_changed = True
    if decision.extracted_end_date:
        if decision.extracted_end_date != ctx.state.get("leave_request_end_date"):
            ctx.state["leave_request_end_date"] = decision.extracted_end_date
            dates_changed = True
    if decision.extracted_reason:
        ctx.state["leave_request_reason"] = decision.extracted_reason
    if decision.extracted_leave_type:
        ctx.state["leave_type_preference"] = decision.extracted_leave_type
    
    if decision.hr_action_type:
        ctx.state["hr_action_type"] = decision.hr_action_type
    if decision.hr_target_employee_id:
        ctx.state["hr_target_employee_id"] = decision.hr_target_employee_id
        
    if dates_changed:
        ctx.state["has_leave_overlap"] = None
        ctx.state["employee_lookup_status"] = None
        ctx.state["holiday_lookup_status"] = None
        # Override action to force it to re-run pipeline on the new dates!
        decision.next_action = "run_pipeline"
        
    ctx.route = decision.next_action
    
    if decision.next_action == "end":
        if ctx.state.get("employee_lookup_status") == "not_found":
            ctx.state["leave_request_employee_id"] = None
            ctx.state["employee_lookup_status"] = None
        return types.Content(role="model", parts=[types.Part(text=decision.missing_info_message)])
    elif decision.next_action == "run_pipeline":
        return types.Content(role="model", parts=[types.Part(text="Fetching your profile and checking the holiday calendar...")])
    elif decision.next_action == "ready_for_calculation":
        return types.Content(role="model", parts=[types.Part(text="Calculating your leave balance and salary deductions...")])
    elif decision.next_action == "submit_leave":
        return types.Content(role="model", parts=[types.Part(text="Finalizing your leave submission...")])
        
    elif decision.next_action == "hr_action":
        return types.Content(role="model", parts=[types.Part(text="Processing HR authorization...")])
        
    return node_input
