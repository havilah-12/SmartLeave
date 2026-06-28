import json
from typing import Any
from datetime import datetime, timedelta
from google.adk.workflow import node
from google.genai import types, Client
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import logger, settings
from database.operations import get_total_holidays_for_year

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

@retry(stop=stop_after_attempt(settings.MAX_RETRIES), wait=wait_exponential(multiplier=1, min=settings.RETRY_MIN_WAIT, max=settings.RETRY_MAX_WAIT), reraise=True)
def _generate_leave_summary(prompt: str) -> str:
    client = Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()

@node(name="calculate_and_format_leave_node")
def calculate_and_format_leave_node(ctx: Any, node_input: Any) -> Any:
    emp_id = ctx.state.get("leave_request_employee_id")
    start_date = ctx.state.get("leave_request_start_date")
    end_date = ctx.state.get("leave_request_end_date")
    reason = ctx.state.get("leave_request_reason", "").lower()
    
    employee = ctx.state.get("employee_details", {})
    holidays = ctx.state.get("holiday_results", [])
    
    # 1. Date math
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception as e:
        return types.Content(role="model", parts=[types.Part(text=f"Error parsing dates: {e}")])
        
    working_days = 0
    holiday_dates = []
    holiday_names = []
    
    weekend_count = 0
    weekend_dates = []
    
    for h in holidays:
        try:
            h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
            if start_dt <= h_date <= end_dt:
                holiday_dates.append(h_date)
                holiday_names.append(f"{h['date']} - {h['name']}")
        except Exception:
            pass
            
    current = start_dt
    while current <= end_dt:
        if current.weekday() >= 5:
            weekend_count += 1
            weekend_dates.append(current.strftime("%Y-%m-%d"))
        elif current not in holiday_dates:
            working_days += 1
        current += timedelta(days=1)
        
    # 2. Policy rules (max 2 per month)
    leaves_this_month = employee.get("leaves_taken_this_month", 0)
    is_emergency = "emergency" in reason.lower() or "medical" in reason.lower() or "hospital" in reason.lower()
    leave_type_preference = ctx.state.get("leave_type_preference", "").lower()
    medical_balance = employee.get("medical_leave_balance", 0)
    
    paid_days = 0
    unpaid_days = 0
    medical_days = 0
    emergency_note = ""

    if leave_type_preference == "medical":
        medical_days = min(working_days, medical_balance)
        emergency_note = f"\n- Company Insurance Policy: NOTIFIED\n- Note: {medical_days} days deducted from your Medical Leave Balance."
        remaining_days = working_days - medical_days
        if remaining_days > 0:
            paid_days_allowed = max(0, 2 - leaves_this_month)
            if remaining_days <= paid_days_allowed:
                paid_days = remaining_days
                emergency_note += f" (Remaining {remaining_days} days covered by regular paid leave)."
            else:
                paid_days = paid_days_allowed
                unpaid_days = remaining_days - paid_days_allowed
                emergency_note += f" (Remaining {remaining_days} days: {paid_days} paid, {unpaid_days} unpaid)."
    elif leave_type_preference == "unpaid":
        paid_days = 0
        unpaid_days = working_days
        if is_emergency:
            emergency_note = "\n- Note: Leave granted as unpaid due to your preference (Medical Emergency)."
    elif is_emergency:
        paid_days_allowed = working_days
        if leaves_this_month >= 2:
            emergency_note = "\n- Note: Leave granted due to emergency health reasons, but will result in loss of pay as you have exceeded your monthly paid limit."
            paid_days = 0
            unpaid_days = working_days
        else:
            paid_days = working_days
            unpaid_days = 0
    else:
        paid_days_allowed = max(0, 2 - leaves_this_month)
        if working_days <= paid_days_allowed:
            paid_days = working_days
        else:
            paid_days = paid_days_allowed
            unpaid_days = working_days - paid_days_allowed

    # 3. Math for salary deduction
    annual_salary = employee.get("salary", 0)
    monthly_salary = annual_salary / 12
    daily_rate = monthly_salary / 30
    deduction = round(daily_rate * unpaid_days, 2)
    final_salary = round(monthly_salary - deduction, 2)
    
    deduction_str = "(NO DEDUCTIONS)" if deduction == 0 else f"(DEDUCTED: {deduction})"
    
    # 4. State updates
    intent = ctx.state.get("intent", "apply_leave")
    
    status = "Approved"
    if not is_emergency and unpaid_days > 2:
        status = "Pending HR Approval"
    
    if intent == "apply_leave":
        ctx.state["pending_submission_payload"] = {
            "employee_id": emp_id,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "total_days": working_days,
            "paid_days": paid_days,
            "unpaid_days": unpaid_days,
            "medical_days": medical_days,
            "status": status
        }
        ctx.state["pending_submission"] = True
        ctx.state["confirmation_status"] = "pending"
        
    ctx.route = "end"
    
    # 5. Build summary with LLM for currency localization
    current_year = datetime.now().strftime("%Y")
    total_holidays_in_year = get_total_holidays_for_year(current_year)
    max_annual_leaves = employee.get("max_annual_leaves", 25)
    country = employee.get("country", "USA")
    
    holiday_str = f"{len(holiday_dates)}"
    if len(holiday_names) > 0:
        holiday_str += f" ({', '.join(holiday_names)})"
        
    weekend_str = f"{weekend_count}"
    if len(weekend_dates) > 0:
        weekend_str += f" ({', '.join(weekend_dates)})"
        
    prompt = f"""You are an HR assistant formatting a leave summary. 
The employee is from: {country}.
Format the following data clearly as a markdown list exactly like the template below. 
CRUCIAL INSTRUCTION 1: For the Final Monthly Salary and Deduction Amount, you MUST use the correct currency symbol for the country '{country}' (e.g., $ for USA, £ for UK, ₹ for India, € for Germany). Do not use the word 'USD' or 'EUR', just the symbol.
CRUCIAL INSTRUCTION 2: Do NOT add any conversational filler at the end like "Would you like to submit this request?" Just output the formatted list.

Data to format:
- Total Holidays this year: {total_holidays_in_year}
- Total Paid leaves of this year: {max_annual_leaves}
- No. of paid leaves per month: 2
- Leaves Taken This Month: {leaves_this_month}
- Holidays in this period: {holiday_str}
- Weekends in this period: {weekend_str}
***
- Requested: {working_days} days
- Paid Leave: {paid_days} days
- Unpaid Leave (Loss of Pay): {unpaid_days} days
- Final Monthly Salary: {final_salary}
- Deduction Amount: {deduction_str}"""

    if status == "Pending HR Approval":
        hr_warning = "\n- HR Review Required: Because this request exceeds 2 unpaid days, it will be routed to HR for manual review."
        prompt += hr_warning

    if emergency_note:
        prompt += f"{emergency_note}"


    try:
        summary = _generate_leave_summary(prompt)
    except Exception as e:
        logger.error(f"API Error generating leave summary: {e}", exc_info=True)
        # Fallback in case of API error
        summary = f"""- Total Holidays this year: {total_holidays_in_year}
- Total Paid leaves of this year: {max_annual_leaves}
- No. of paid leaves per month: 2
- Leaves Taken This Month: {leaves_this_month}
- Holidays in this period: {holiday_str}
- Weekends in this period: {weekend_str}
***
- Requested: {working_days} days
- Paid Leave: {paid_days} days
- Unpaid Leave (Loss of Pay): {unpaid_days} days
- IN-HAND SALARY OF THIS MONTH WILL BE: {final_salary} {deduction_str}{emergency_note}"""
        if status == "Pending HR Approval":
            summary += "\n- HR Review Required: Because this request exceeds 2 unpaid days, it will be routed to HR for manual review."

    if intent == "apply_leave":
        submit_q = "Do you want to submit this request for HR review? (Yes/No)" if status == "Pending HR Approval" else "Do you want to submit this request? (Yes/No)"
        summary += f"\n\n{submit_q}"

    return types.Content(role="model", parts=[types.Part(text=summary)])

@node(name="prepare_confirmation_node")
def prepare_confirmation_node(ctx: Any, node_input: Any) -> Any:
    text = ctx.state.get("calculation_raw_results", "")
    employee = ctx.state.get("employee_details", {})
    holidays = ctx.state.get("holiday_results", [])
    
    instruction = f"""[SYSTEM DELEGATION]
Please format the final summary for the user and ask them to confirm if they want to submit.
Employee Details: {json.dumps(employee)}
Holidays: {json.dumps(holidays)}
Calculation Math: {text}
"""
    ctx.state["pending_submission"] = True
    ctx.state["confirmation_status"] = "pending"
    ctx.route = "continue"
    return types.Content(role="user", parts=[types.Part(text=instruction)])
