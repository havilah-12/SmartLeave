from google.adk.agents.context import Context
from database.operations import get_employee_details as fetch_employee

def get_employee_details(employee_id: str, tool_context: Context) -> dict:
    """Retrieve employee details including leave balance and leaves taken this month."""
    details = fetch_employee(employee_id)
    
    if "error" in details:
        tool_context.state["employee_lookup_status"] = "not_found"
    else:
        tool_context.state["employee_details"] = details
        tool_context.state["employee_lookup_status"] = "found"
        
    return details
