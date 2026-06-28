import json
from datetime import datetime, timedelta
from typing import List, Dict

def calculate_working_days(start_date: str, end_date: str, holidays_list: List[Dict[str, str]], reason: str) -> str:
    """Computes the exact working days for a leave request, excluding weekends and public holidays.
    Args:
        start_date: start date in YYYY-MM-DD
        end_date: end date in YYYY-MM-DD
        holidays_list: List of holiday dicts e.g. [{"date": "2026-01-01", "name": "New Year"}]
        reason: the reason for the leave
    Returns:
        JSON string containing the calculation breakdown.
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception as e:
        return json.dumps({"error": f"Invalid date format. Use YYYY-MM-DD. Details: {e}"})

    if start_dt > end_dt:
        return json.dumps({"error": "Start date cannot be after end date."})

    working_days = 0
    weekend_days = 0
    holidays_excluded = 0
    
    current_date = start_dt
    holiday_dates = []
    for h in holidays_list:
        try:
            holiday_dates.append(datetime.strptime(h["date"], "%Y-%m-%d").date())
        except Exception:
            pass

    while current_date <= end_dt:
        if current_date.weekday() >= 5:
            weekend_days += 1
        elif current_date in holiday_dates:
            holidays_excluded += 1
        else:
            working_days += 1
        current_date += timedelta(days=1)

    return json.dumps({
        "total_days": working_days,
        "weekends_excluded": weekend_days,
        "holidays_excluded": holidays_excluded,
        "final_leave_days": working_days
    })

def stage_policy_evaluation(paid_days: int, unpaid_days: int) -> str:
    """Use this tool to submit your final policy decision.
    Args:
        paid_days: number of paid leave days
        unpaid_days: number of unpaid leave days
    Returns:
        A formatted string that you MUST include directly in your output.
    """
    payload = {
        "paid_days": paid_days,
        "unpaid_days": unpaid_days
    }
    return f"\n\n---POLICY DECISION---\n{json.dumps(payload)}\n---------------------\n"
