from typing import Any
from google.adk.workflow import node
from google.genai import types

@node(name="validation_node")
def validation_node(ctx: Any, node_input: Any) -> Any:
    """A fast deterministic python node that bypasses the LLM router to validate the pipeline results."""
    
    lookup_status = ctx.state.get("employee_lookup_status")
    has_overlap = ctx.state.get("has_leave_overlap")
    
    if lookup_status == "not_found":
        ctx.route = "end"
        return types.Content(role="model", parts=[types.Part(text="I couldn't find that Employee ID in the system. Please provide a valid Employee ID.")])
        
    if has_overlap:
        ctx.route = "end"
        return types.Content(role="model", parts=[types.Part(text="It looks like you already have an overlapping leave scheduled for these dates. Please pick new dates.")])
        
    # If all valid, fast-track straight to the calculation phase!
    ctx.route = "continue"
    return types.Content(role="model", parts=[types.Part(text="")])
