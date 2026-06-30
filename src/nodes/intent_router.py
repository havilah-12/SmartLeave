import json
from typing import Any
from pydantic import BaseModel, Field
from google.adk.workflow import node
from google.genai import types, Client

from config.settings import settings, logger

class RouterDecision(BaseModel):
    next_action: str = Field(description="One of: 'run_pipeline', 'continue_calculation', 'submit_leave', 'hr_action', 'end'")
    missing_info_message: str = Field(description="If 'end', the message to display to the user.")
    extracted_employee_id: str = Field(description="Employee ID if found in history")
    extracted_start_date: str = Field(description="Start Date (YYYY-MM-DD) if found")
    extracted_end_date: str = Field(description="End Date (YYYY-MM-DD) if found")
    extracted_reason: str = Field(description="Reason for leave if found")
    extracted_leave_type: str = Field(description="paid, unpaid, or medical. Empty if not yet provided.")
    hr_action_type: str = Field(description="If next_action is 'hr_action', one of: 'approve', 'reject'. Empty otherwise.")
    hr_target_employee_id: str = Field(description="If next_action is 'hr_action', the employee ID they are taking action on.")
    hr_passcode: str = Field(default="", description="If next_action is 'hr_action', the 6-character unique passcode provided by the HR.")
    is_revoke_intent: bool = Field(default=False, description="True if the user wants to cancel or revoke an existing leave.")

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
        "preview_status": ctx.state.get("preview_status"),
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
1. If the user states they are HR (e.g. "I am HR001") AND asks to approve or reject/cancel a pending leave for another employee (e.g. "Approve EMP009's leave") AND provides their passcode (e.g. "passcode SAR123"): output next_action='hr_action', extract their HR ID into 'extracted_employee_id', their passcode into 'hr_passcode', set 'hr_action_type' to 'approve' or 'reject', and set 'hr_target_employee_id'.
2. If preview_status is 'pending' and the user confirms they approve the Paid/Unpaid breakdown, output next_action='continue_calculation'. If they decline and specify a new preference (e.g. "make it unpaid"), extract the new preference into 'extracted_leave_type' and output next_action='run_pipeline'.
3. If confirmation_status is 'pending' and the user confirms they want to submit (e.g., 'yes', 'do it'), output next_action='submit_leave'. If they decline (e.g., 'no', 'cancel'), output next_action='end' and say it was cancelled.
4. If the user wants to revoke or cancel an existing leave: you MUST have their Employee ID and the Start Date of the leave. If either is missing, output next_action='end' and ask for the missing details. If both are present, output next_action='submit_leave' and set is_revoke_intent=true.
5. STRICT RULE: For APPLYING for a new leave, you MUST have Employee ID, Start Date, End Date, AND Reason. If ANY of these 4 are missing, output next_action='end' and ask the user for the missing ones. Do NOT output run_pipeline if they are missing!
6. If ALL 4 required slots are present for a new leave and preview_status is NOT pending and confirmation_status is NOT pending, output next_action='run_pipeline'.
6. If it's just a greeting or unrelated, output next_action='end' and provide a greeting in missing_info_message. It MUST say exactly: 'Hi, I'm your Smart Leave Assistant! I can help you easily apply for leave, check your balances, and cancel existing requests.'

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
    if hasattr(decision, 'hr_passcode') and decision.hr_passcode:
        ctx.state["hr_passcode"] = decision.hr_passcode
        
    if dates_changed:
        ctx.state["has_leave_overlap"] = None
        
        # If employee is already found, we can just fetch holidays and check overlap here to avoid LLM calls
        if ctx.state.get("employee_lookup_status") == "found":
            from database.operations import get_holidays, check_leave_overlap
            
            has_overlap = check_leave_overlap(
                ctx.state["leave_request_employee_id"], 
                ctx.state["leave_request_start_date"], 
                ctx.state["leave_request_end_date"]
            )
            ctx.state["has_leave_overlap"] = has_overlap
            
            holidays = get_holidays(
                ctx.state["leave_request_start_date"], 
                ctx.state["leave_request_end_date"]
            )
            ctx.state["holiday_results"] = holidays
            
            if has_overlap:
                decision.next_action = "end"
                decision.missing_info_message = "It looks like you already have an overlapping leave scheduled for these dates. Please pick new dates."
            else:
                decision.next_action = "continue_calculation"
        else:
            ctx.state["employee_lookup_status"] = None
            ctx.state["holiday_lookup_status"] = None
            # Override action to force it to re-run pipeline on the new dates!
            decision.next_action = "run_pipeline"
        
    if decision.next_action == "continue_calculation":
        ctx.state["breakdown_confirmed"] = True
        ctx.state["preview_status"] = None
        
    ctx.route = decision.next_action
    
    if decision.next_action == "end":
        if ctx.state.get("employee_lookup_status") == "not_found":
            ctx.state["leave_request_employee_id"] = None
            ctx.state["employee_lookup_status"] = None
        return types.Content(role="model", parts=[types.Part(text=decision.missing_info_message)])
    elif decision.next_action == "run_pipeline":
        ctx.state["preview_status"] = None
        return types.Content(role="model", parts=[types.Part(text="Fetching your profile, checking the holiday calendar, and calculating your leave balance...")])
    elif decision.next_action == "continue_calculation":
        if dates_changed:
            return types.Content(role="model", parts=[types.Part(text="Recalculating your leave breakdown for the new dates...")])
        return types.Content(role="model", parts=[types.Part(text="Calculating final salary deductions...")])
    elif decision.next_action == "submit_leave":
        if decision.is_revoke_intent:
            return types.Content(role="model", parts=[types.Part(text="Processing your leave revocation...")])
        else:
            return types.Content(role="model", parts=[types.Part(text="Finalizing your leave submission...")])
        
    elif decision.next_action == "hr_action":
        return types.Content(role="model", parts=[types.Part(text="Processing HR authorization...")])
        
    return node_input
