from google.adk.agents.context import Context
from database.operations import get_holidays as fetch_holidays, get_total_holidays_for_year
from datetime import datetime, timedelta

def get_holidays(tool_context: Context) -> dict:
    """Retrieve public holidays, weekends, and total holidays for the year for the requested leave dates."""
    
    start_date = tool_context.state.get("leave_request_start_date")
    end_date = tool_context.state.get("leave_request_end_date")
    
    if not start_date or not end_date:
        return {"error": "Missing leave dates in state"}
    
    holidays = fetch_holidays(start_date, end_date)
    tool_context.state["holiday_results"] = holidays
    tool_context.state["holiday_lookup_status"] = "found"
    
    # Calculate weekends
    weekend_count = 0
    weekend_dates = []
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        current = start_dt
        while current <= end_dt:
            if current.weekday() >= 5:
                weekend_count += 1
                weekend_dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
    except Exception:
        pass
        
    current_year = datetime.now().strftime("%Y")
    yearly_holidays_list = get_total_holidays_for_year(current_year)
    
    return {
        "holidays_in_period": holidays,
        "weekends_count": weekend_count,
        "weekend_dates": weekend_dates,
        "total_holidays_this_year_count": len(yearly_holidays_list),
        "yearly_holidays_list": yearly_holidays_list
    }
