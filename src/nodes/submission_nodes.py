from typing import Any
from datetime import datetime
from google.adk.workflow import node
from google.genai import types

from database.operations import save_leave_application, revoke_leave

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

@node(name="revoke_leave_node")
def revoke_leave_node(ctx: Any, node_input: Any) -> Any:
    emp_id = ctx.state.get("leave_request_employee_id")
    target_date = ctx.state.get("leave_request_start_date")
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    result = revoke_leave(emp_id, target_date, current_date)
    ctx.route = "end"
    
    if result["status"] == "SUCCESS":
        return types.Content(role="model", parts=[types.Part(text=f"✅ {result['message']}")])
    else:
        return types.Content(role="model", parts=[types.Part(text=f"❌ Failed to revoke leave: {result['message']}")])
