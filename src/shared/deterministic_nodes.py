import re
from typing import Any
from datetime import datetime, timedelta
from google.adk.workflow import node
from google.genai import types

from database.operations import save_leave_application, get_employee_details, get_holidays

@node(name="missing_info_router")
def missing_info_router(ctx: Any, node_input: Any) -> Any:
    """Check if any required slots are missing and route accordingly."""
    intent = ctx.state.get("intent", "apply_leave")
    
    if intent not in ["apply_leave", "calculate_only"]:
        ctx.route = intent
        # Inject today's date so the agents know the current year/date
        today = datetime.now().strftime("%Y-%m-%d")
        if hasattr(node_input, "parts"):
            node_input.parts.append(types.Part(text=f"\n[SYSTEM: Today's Date is {today}]"))
        return node_input
        
    missing = []
    if not ctx.state.get("leave_request_employee_id"):
        missing.append("employee_id")
    if not ctx.state.get("leave_request_start_date"):
        missing.append("start_date")
    if not ctx.state.get("leave_request_end_date"):
        missing.append("end_date")
    if not ctx.state.get("leave_request_reason"):
        missing.append("reason")
        
    ctx.state["missing_fields"] = missing
    
    if missing:
        ctx.route = "incomplete_request"
    else:
        ctx.route = "ready_for_pipeline"
        
    return f"Missing slots checked: {len(missing)} missing"

@node(name="ask_missing_info")
def ask_missing_info(ctx: Any, node_input: Any) -> types.Content:
    """Conversational node to prompt the user precisely for missing fields."""
    missing = ctx.state.get("missing_fields", [])
    
    parts = []
    if "employee_id" in missing:
        parts.append("your Employee ID")
    if "start_date" in missing and "end_date" in missing:
        parts.append("the start and end dates")
    elif "start_date" in missing:
        parts.append("the start date")
    elif "end_date" in missing:
        parts.append("the end date")
    if "reason" in missing:
        parts.append("the reason for your leave")
        
    if len(parts) == 1:
        msg = f"Please provide {parts[0]}."
    elif len(parts) == 2:
        msg = f"Please provide {parts[0]} and {parts[1]}."
    else:
        msg = f"Please provide {', '.join(parts[:-1])}, and {parts[-1]}."
        
    ctx.route = "end"
    return types.Content(role="model", parts=[types.Part(text=msg)])

@node(name="employee_lookup_node")
def employee_lookup_node(ctx: Any, node_input: Any) -> Any:
    employee_id = ctx.state.get("leave_request_employee_id")
    if not employee_id:
        ctx.state["employee_lookup_status"] = "not_found"
        return "Employee ID not found in state"
        
    details = get_employee_details(employee_id)
    if "error" in details:
        ctx.state["employee_lookup_status"] = "not_found"
    else:
        ctx.state["employee_details"] = details
        ctx.state["employee_lookup_status"] = "found"
        
    return f"Employee lookup: {ctx.state['employee_lookup_status']}"

@node(name="holiday_lookup_node")
def holiday_lookup_node(ctx: Any, node_input: Any) -> Any:
    start_date = ctx.state.get("leave_request_start_date")
    end_date = ctx.state.get("leave_request_end_date")
    if not start_date or not end_date:
        ctx.state["holiday_lookup_status"] = "not_found"
        return "Missing dates for holiday lookup"
        
    holidays = get_holidays(start_date, end_date)
    ctx.state["holiday_results"] = holidays
    ctx.state["holiday_lookup_status"] = "found"
    return f"Found {len(holidays)} holidays"

@node(name="calculator_node")
def calculator_node(ctx: Any, node_input: Any) -> Any:
    """Deterministic math node: Calculates total working days, excluding weekends and holidays."""
    start_date_str = ctx.state.get("leave_request_start_date")
    end_date_str = ctx.state.get("leave_request_end_date")
    holidays = ctx.state.get("holiday_results", [])
    
    if not start_date_str or not end_date_str:
        ctx.route = "error"
        return "Error: Missing dates for calculation."
        
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except Exception as e:
        ctx.route = "error"
        return f"Error parsing dates: {e}"

    if start_date > end_date:
        ctx.route = "error"
        return "Error: Start date cannot be after end date."

    working_days = 0
    weekend_days = 0
    holidays_excluded = 0
    
    current_date = start_date
    holiday_dates = [datetime.strptime(h["date"], "%Y-%m-%d").date() for h in holidays]

    while current_date <= end_date:
        if current_date.weekday() >= 5:
            weekend_days += 1
        elif current_date in holiday_dates:
            holidays_excluded += 1
        else:
            working_days += 1
        current_date += timedelta(days=1)

    ctx.state["calculated_total_days"] = working_days
    ctx.state["calculated_weekend_days"] = weekend_days
    ctx.state["calculated_holidays_excluded"] = holidays_excluded
    ctx.route = "continue"
    return f"Calculated {working_days} working days"

@node(name="policy_node")
def policy_node(ctx: Any, node_input: Any) -> Any:
    """Deterministic policy rules engine."""
    employee = ctx.state.get("employee_details", {})
    total_days = ctx.state.get("calculated_total_days", 0)
    reason = ctx.state.get("leave_request_reason", "").lower()
    
    balance = employee.get("leave_balance", 0)
    leaves_this_month = employee.get("leaves_taken_this_month", 0)
    
    # 1. Simple balance check
    if total_days > balance:
        ctx.state["policy_status"] = "rejected"
        ctx.state["policy_message"] = f"Insufficient annual leave balance. Requested {total_days}, but only have {balance} days remaining."
        ctx.state["calculated_paid_days"] = 0
        ctx.state["calculated_unpaid_days"] = total_days
        ctx.route = "rejected"
        return "Policy: Rejected due to insufficient balance"

    # 2. Emergency reasoning fallback logic (simplified for deterministic node)
    # If the user says it's a medical emergency, allow overriding the monthly limit
    is_emergency = "emergency" in reason or "hospital" in reason or "accident" in reason

    # 3. Monthly limit check (Max 3 days per month for non-emergencies)
    if not is_emergency and leaves_this_month + total_days > 3:
        paid_days_allowed = max(0, 3 - leaves_this_month)
        unpaid_days = total_days - paid_days_allowed
        
        ctx.state["calculated_paid_days"] = paid_days_allowed
        ctx.state["calculated_unpaid_days"] = unpaid_days
        ctx.state["policy_status"] = "needs_review"
        ctx.state["policy_message"] = f"Monthly limit of 3 paid leaves exceeded. {paid_days_allowed} days will be paid, {unpaid_days} days will be unpaid."
        ctx.route = "continue"
        return "Policy: Exceeded monthly limit, partial pay"
        
    # Happy Path
    ctx.state["calculated_paid_days"] = total_days
    ctx.state["calculated_unpaid_days"] = 0
    ctx.state["policy_status"] = "eligible"
    ctx.state["policy_message"] = "Leave request is eligible and fully paid."
    ctx.route = "continue"
    return "Policy: Eligible and fully paid"

@node(name="leave_summary_node")
def leave_summary_node(ctx: Any, node_input: Any) -> types.Content:
    """Builds the final frozen payload and stages it for confirmation."""
    payload = {
        "employee_id": ctx.state.get("leave_request_employee_id"),
        "start_date": ctx.state.get("leave_request_start_date"),
        "end_date": ctx.state.get("leave_request_end_date"),
        "reason": ctx.state.get("leave_request_reason"),
        "total_days": ctx.state.get("calculated_total_days"),
        "paid_days": ctx.state.get("calculated_paid_days"),
        "unpaid_days": ctx.state.get("calculated_unpaid_days"),
    }
    
    ctx.state["pending_submission_payload"] = payload
    ctx.state["pending_submission"] = True
    ctx.state["confirmation_status"] = "pending"
    ctx.route = "end"
    
    employee = ctx.state.get("employee_details", {})
    balance = employee.get("leave_balance", 0)
    leaves_this_month = employee.get("leaves_taken_this_month", 0)
    leaves_this_year = employee.get("leaves_taken_this_year", 0)
    
    weekends_excluded = ctx.state.get("calculated_weekend_days", 0)
    holidays_excluded = ctx.state.get("calculated_holidays_excluded", 0)
    
    summary = f"""**Leave Calculation Breakdown:**
- **Requested Dates:** {payload['start_date']} to {payload['end_date']}
- **Total Working Days:** {payload['total_days']}
- **Weekends Excluded (Sat/Sun):** {weekends_excluded}
- **Public Holidays Excluded:** {holidays_excluded}

**Leave Balances:**
- **Leaves Taken This Year (YTD):** {leaves_this_year} (Total Balance: {balance})
- **Leaves Taken This Month:** {leaves_this_month}

**Policy Evaluation:**
{ctx.state.get("policy_message")}

Do you want me to submit this leave request? (Yes/No)"""

    return types.Content(role="model", parts=[types.Part(text=summary)])

@node(name="submit_leave_node")
def submit_leave_node(ctx: Any, node_input: Any) -> types.Content:
    """Deterministic database persistence node."""
    payload = ctx.state.get("pending_submission_payload")
    if not payload:
        return types.Content(role="model", parts=[types.Part(text="Error: No pending submission payload found.")])
        
    result = save_leave_application(**payload)
    
    # Clear the payload after successful submission
    ctx.state["pending_submission"] = False
    ctx.state["pending_submission_payload"] = None
    
    return types.Content(role="model", parts=[types.Part(text=f"{result['message']}")])

import json

@node(name="prepare_calculation_context")
def prepare_calculation_context(ctx: Any, node_input: Any) -> Any:
    employee = ctx.state.get("employee_details", {})
    holidays = ctx.state.get("holiday_results", [])
    start = ctx.state.get("leave_request_start_date")
    end = ctx.state.get("leave_request_end_date")
    reason = ctx.state.get("leave_request_reason")
    
    instruction = f"""[SYSTEM DELEGATION]
Please calculate the working days and evaluate the policy.
Today's Date: {datetime.now().strftime("%Y-%m-%d")}
Employee Details: {json.dumps(employee)}
Holidays: {json.dumps(holidays)}
Start Date: {start}
End Date: {end}
Reason: {reason}
"""
    return types.Content(role="user", parts=[types.Part(text=instruction)])

@node(name="extract_calculation_payload")
def extract_calculation_payload(ctx: Any, node_input: Any) -> Any:
    text = getattr(node_input.parts[0], "text", "") if hasattr(node_input, "parts") else str(node_input)
    ctx.state["calculation_raw_results"] = text
    
    match = re.search(r"---POLICY DECISION---\n(.*?)\n---------------------", text, re.DOTALL)
    if match:
        try:
            decision = json.loads(match.group(1))
            paid = decision.get("paid_days", 0)
            unpaid = decision.get("unpaid_days", 0)
            
            payload = {
                "employee_id": ctx.state.get("leave_request_employee_id"),
                "start_date": ctx.state.get("leave_request_start_date"),
                "end_date": ctx.state.get("leave_request_end_date"),
                "reason": ctx.state.get("leave_request_reason"),
                "total_days": paid + unpaid,
                "paid_days": paid,
                "unpaid_days": unpaid,
            }
            ctx.state["pending_submission_payload"] = payload
        except Exception:
            pass

    ctx.route = "continue"
    return node_input

@node(name="prepare_submission_context")
def prepare_submission_context(ctx: Any, node_input: Any) -> Any:
    text = ctx.state.get("calculation_raw_results", "")
    employee = ctx.state.get("employee_details", {})
    holidays = ctx.state.get("holiday_results", [])
    
    instruction = f"""[SYSTEM DELEGATION]
Please format the leave submission summary.
Employee Details: {json.dumps(employee)}
Holidays: {json.dumps(holidays)}
Raw Calculation Results: {text}
"""
    ctx.state["pending_submission"] = True
    ctx.state["confirmation_status"] = "pending"
    ctx.route = "continue"
    return types.Content(role="user", parts=[types.Part(text=instruction)])
