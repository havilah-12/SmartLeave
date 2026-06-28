import json
import re
from typing import Any
from datetime import datetime, timedelta
from google.adk.workflow import node

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

    # 3. Monthly limit check (Max 2 days per month for non-emergencies)
    if not is_emergency and leaves_this_month + total_days > 2:
        paid_days_allowed = max(0, 2 - leaves_this_month)
        unpaid_days = total_days - paid_days_allowed
        
        ctx.state["calculated_paid_days"] = paid_days_allowed
        ctx.state["calculated_unpaid_days"] = unpaid_days
        ctx.state["policy_message"] = f"Monthly limit of 2 paid leaves exceeded. {paid_days_allowed} days will be paid, {unpaid_days} days will be unpaid."
        ctx.route = "continue"
        return "Policy: Exceeded monthly limit, partial pay"
        
    # Happy Path
    ctx.state["calculated_paid_days"] = total_days
    ctx.state["calculated_unpaid_days"] = 0
    ctx.state["policy_status"] = "eligible"
    ctx.state["policy_message"] = "Leave request is eligible and fully paid."
    ctx.route = "continue"
    return "Policy: Eligible and fully paid"

@node(name="leave_balance_check_node")
def leave_balance_check_node(ctx: Any, node_input: Any) -> Any:
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
