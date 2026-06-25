from google.adk.agents.context import Context
from database.operations import get_holidays as fetch_holidays

def get_holidays(start_date: str, end_date: str, tool_context: Context) -> list[dict]:
    """Retrieve public holidays within a specific date range, including their names."""
    tool_context.state["leave_request_start_date"] = start_date
    tool_context.state["leave_request_end_date"] = end_date
    
    holidays = fetch_holidays(start_date, end_date)
    tool_context.state["holiday_results"] = holidays
    tool_context.state["holiday_lookup_status"] = "found"
    
    return holidays
