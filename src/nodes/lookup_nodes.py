from typing import Any
from google.adk.workflow import node
from database.operations import get_employee_details, get_holidays, check_leave_overlap

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

@node(name="fetch_existing_leaves_node")
def fetch_existing_leaves_node(ctx: Any, node_input: Any) -> Any:
    emp_id = ctx.state.get("leave_request_employee_id")
    start = ctx.state.get("leave_request_start_date")
    end = ctx.state.get("leave_request_end_date")
    
    if emp_id and start and end:
        has_overlap = check_leave_overlap(emp_id, start, end)
        ctx.state["has_leave_overlap"] = has_overlap
    else:
        ctx.state["has_leave_overlap"] = False
        
    return "Existing leaves fetched"
