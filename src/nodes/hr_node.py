from typing import Any
from google.adk.workflow import node
from google.genai import types
from database.operations import process_hr_approval

@node(name="hr_node")
def hr_node(ctx: Any, node_input: Any) -> Any:
    hr_emp_id = ctx.state.get("leave_request_employee_id")
    action_type = ctx.state.get("hr_action_type")
    target_emp_id = ctx.state.get("hr_target_employee_id")
    
    if not hr_emp_id or not action_type or not target_emp_id:
        return types.Content(role="model", parts=[types.Part(text="Missing HR authorization or target employee ID.")])
        
    result = process_hr_approval(hr_emp_id, target_emp_id, action_type)
    
    if "error" in result:
        return types.Content(role="model", parts=[types.Part(text=f"**HR Action Failed:** {result['error']}")])
        
    action_word = "approved" if result["new_status"] == "Approved" else "rejected"
    msg = f"**Successfully {action_word} pending leave for {target_emp_id} ({result['name']}).**\n\nAn automated email notification has been dispatched to `{result['email']}`."
    
    # Clear HR action state
    ctx.state["hr_action_type"] = None
    ctx.state["hr_target_employee_id"] = None
    
    return types.Content(role="model", parts=[types.Part(text=msg)])
