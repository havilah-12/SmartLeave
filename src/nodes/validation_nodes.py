from typing import Any
from datetime import datetime
from google.adk.workflow import node
from google.genai import types, Client
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import logger, settings
from database.operations import get_employee_details

@node(name="validate_request_node")
def validate_request_node(ctx: Any, node_input: Any) -> Any:
    """Check if any required slots are missing and route accordingly."""
    intent = ctx.state.get("intent", "apply_leave")
    
    if intent == "unknown":
        ctx.route = "greeting"
        return node_input
        
    if intent not in ["apply_leave", "calculate_only", "revoke_leave"]:
        ctx.route = intent
        # Inject today's date so the agents know the current year/date
        today = datetime.now().strftime("%Y-%m-%d")
        if hasattr(node_input, "parts"):
            node_input.parts.append(types.Part(text=f"\n[SYSTEM: Today's Date is {today}]"))
        return node_input
        
    missing = []
    
    emp_id = ctx.state.get("leave_request_employee_id")
    if not emp_id:
        missing.append("Employee ID")
    else:
        details = get_employee_details(emp_id)
        if "error" in details:
            ctx.route = "end"
            return types.Content(role="model", parts=[types.Part(text=f"I'm sorry, I could not find any details for Employee ID: {emp_id}. Please check your Employee ID and try again.")])
            
    if not ctx.state.get("leave_request_start_date"):
        missing.append("Target Date / Start Date")
        
    if intent in ["apply_leave", "calculate_only"]:
        if not ctx.state.get("leave_request_end_date"):
            missing.append("End Date")
        if not ctx.state.get("leave_request_reason") and intent == "apply_leave":
            missing.append("Reason")
            
    if missing:
        ctx.state["missing_slots"] = missing
        ctx.route = "incomplete_request"
    else:
        if intent == "revoke_leave":
            ctx.route = "revoke_leave"
        else:
            ctx.route = "ready_for_pipeline"
            
    return f"Missing slots checked: {len(missing)} missing"

@retry(stop=stop_after_attempt(settings.MAX_RETRIES), wait=wait_exponential(multiplier=1, min=settings.RETRY_MIN_WAIT, max=settings.RETRY_MAX_WAIT), reraise=True)
def _generate_missing_info_prompt(missing: list) -> str:
    client = Client(api_key=settings.GEMINI_API_KEY)
    prompt = f"You are a helpful HR assistant. The user wants to proceed with their leave request but the following information is missing: {', '.join(missing)}. Politely ask the user to provide this specific missing information. Keep it brief and natural."
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

@node(name="greeting_node")
def greeting_node(ctx: Any, node_input: Any) -> Any:
    ctx.route = "end"
    msg = "Hello! I am the SmartLeave Assistant. I can help you apply for leave, check your balance, check company holidays, or revoke an existing leave. How can I assist you today?"
    return types.Content(role="model", parts=[types.Part(text=msg)])

@node(name="ask_missing_info")
def ask_missing_info(ctx: Any, node_input: Any) -> types.Content:
    """Conversational node to prompt the user precisely for missing fields using an LLM."""
    missing = ctx.state.get("missing_slots", [])
    
    if not missing:
        msg = "Please provide the missing information."
    else:
        try:
            msg = _generate_missing_info_prompt(missing)
        except Exception as e:
            logger.error(f"API Error generating missing info prompt: {e}", exc_info=True)
            msg = f"Please provide the following missing information: {', '.join(missing)}."
            
    ctx.route = "end"
    return types.Content(role="model", parts=[types.Part(text=msg)])

@node(name="overlap_check_node")
def overlap_check_node(ctx: Any, node_input: Any) -> Any:
    if ctx.state.get("has_leave_overlap"):
        ctx.route = "overlapping_leave_error"
        return types.Content(role="model", parts=[types.Part(text="Error: The requested dates overlap with an already approved leave. Please choose different dates.")])
    
    ctx.route = "continue"
    return "No overlapping leaves found"

@node(name="check_leave_preference_node")
def check_leave_preference_node(ctx: Any, node_input: Any) -> Any:
    intent = ctx.state.get("intent")
    if intent not in ["apply_leave", "calculate_only"]:
        ctx.route = "continue"
        return "Leave preference skipped (not applicable)"
        
    employee = ctx.state.get("employee_details", {})
    balance = employee.get("leave_balance", 0)
    medical_balance = employee.get("medical_leave_balance", 0)
    pref = ctx.state.get("leave_type_preference")
    
    reason = ctx.state.get("leave_request_reason", "").lower()
    is_emergency = "emergency" in reason or "medical" in reason or "hospital" in reason
    
    if is_emergency and medical_balance > 0 and pref not in ["medical", "unpaid", "paid"]:
        ctx.state["missing_slots"] = [f"Leave Type Preference (You have {medical_balance} Medical Leave days available. Do you want to use your Medical Leave for this emergency, or use standard paid/unpaid leave?)"]
        ctx.route = "ask_preference"
        return "Asking user for medical leave preference"
    
    if balance > 0 and not pref:
        ctx.state["missing_slots"] = ["Leave Type Preference (You have paid leave available. Do you want to use your paid balance, or take this as unpaid leave?)"]
        ctx.route = "ask_preference"
        return "Asking user for leave preference"
        
    ctx.route = "continue"
    return "Leave preference verified"

@node(name="readiness_check_node")
def readiness_check_node(ctx: Any, node_input: Any) -> Any:
    """Check if the employee and holidays were found."""
    employee_ok = ctx.state.get("employee_lookup_status") == "found"
    holiday_ok = ctx.state.get("holiday_lookup_status") == "found"

    if not employee_ok:
        ctx.route = "employee_error"
        return types.Content(role="model", parts=[types.Part(text="Error: Could not find your employee details.")])
    elif not holiday_ok:
        ctx.route = "holiday_error"
        return types.Content(role="model", parts=[types.Part(text="Error: Could not retrieve holiday calendar.")])
    else:
        ctx.route = "ready"
        return "System ready for calculations"

@node(name="check_employee_intent")
def check_employee_intent(ctx: Any, node_input: Any) -> Any:
    if ctx.state.get("intent") == "employee_only":
        ctx.route = "end"
    else:
        ctx.route = "continue"
    return "Employee logic complete"

@node(name="check_holiday_intent")
def check_holiday_intent(ctx: Any, node_input: Any) -> Any:
    if ctx.state.get("intent") == "holiday_only":
        ctx.route = "end"
    else:
        ctx.route = "continue"
    return "Holiday logic complete"
