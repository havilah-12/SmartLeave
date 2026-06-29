from google.adk.agents.context import Context
from nodes.formatting_nodes import calculate_and_format_leave_node
from google.genai import types

def calculate_leave(tool_context: Context) -> str:
    """Calculates the working days, leave limits, and salary deductions based on HR policy."""
    res = calculate_and_format_leave_node(tool_context, None)
    if isinstance(res, types.Content):
        return res.parts[0].text
    return str(res)
