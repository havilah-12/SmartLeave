from google.adk.agents.context import Context
from nodes.submission_nodes import submit_leave_node, revoke_leave_node
from google.genai import types

def submit_leave(tool_context: Context) -> str:
    """Submits the pending leave request to the database."""
    res = submit_leave_node(tool_context, None)
    if isinstance(res, types.Content):
        return res.parts[0].text
    return str(res)

def revoke_leave(tool_context: Context) -> str:
    """Revokes and deletes an existing leave request from the database."""
    res = revoke_leave_node(tool_context, None)
    if isinstance(res, types.Content):
        return res.parts[0].text
    return str(res)
