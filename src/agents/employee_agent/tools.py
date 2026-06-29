from google.adk.agents.context import Context
from database.operations import get_employee_details as fetch_employee
from nodes.lookup_nodes import fetch_existing_leaves_node

def get_employee_details(tool_context: Context) -> dict:
    """Retrieve employee details including leave balance and leaves taken this month."""
    employee_id = tool_context.state.get("leave_request_employee_id")
    if not employee_id:
        return {"error": "No employee ID found in state"}
        
    details = fetch_employee(employee_id)
    
    if "error" in details:
        tool_context.state["employee_lookup_status"] = "not_found"
    else:
        tool_context.state["employee_details"] = details
        tool_context.state["employee_lookup_status"] = "found"
        
    return details

def lookup_existing_leaves(tool_context: Context) -> str:
    """Checks the database to see if the employee has any existing overlapping leaves."""
    res = fetch_existing_leaves_node(tool_context, None)
    return "Successfully checked for existing leaves. The overlap status has been updated in the system."
